from __future__ import annotations

import logging
from decimal import Decimal

from catalog.models import Product
from core.models import BusinessLunchDay
from django.db import transaction

from integrations.telegram.client import TelegramError, edit_message_text
from integrations.telegram.client import send_message
from .models import OnlinePaymentAttempt, Order, OrderItem
from .notifications import build_order_status_keyboard, format_new_order_message

logger = logging.getLogger(__name__)
ZERO_AMOUNT = Decimal("0.00")


def _money(value: Decimal | str | int | float | None) -> Decimal:
    if value in (None, ""):
        return ZERO_AMOUNT
    return Decimal(str(value)).quantize(Decimal("0.01"))


def _coord(value: Decimal | str | int | float | None) -> Decimal | None:
    if value in (None, ""):
        return None
    return Decimal(str(value)).quantize(Decimal("0.000001"))


def serialize_cart_lines(lines) -> list[dict]:
    snapshot = []

    for line in lines:
        item = {
            "kind": line.kind,
            "product_name": "",
            "unit_price": str(_money(line.unit_price)),
            "quantity": int(line.qty),
            "line_total": str(_money(line.line_total)),
        }

        if line.kind == "product" and line.product:
            item["product_id"] = line.product.id
            item["product_name"] = line.product.name
        elif line.kind == "business_lunch" and line.lunch_day:
            item["lunch_day_id"] = line.lunch_day.id
            item["product_name"] = line.lunch_day.display_name
        else:
            continue

        snapshot.append(item)

    return snapshot


def create_order_from_snapshot(
    *,
    fulfillment: str,
    payment_method: str,
    customer_name: str,
    customer_phone: str,
    customer_comment: str = "",
    address_line: str = "",
    address_entrance: str = "",
    address_floor: str = "",
    address_apartment: str = "",
    delivery_lat: Decimal | str | int | float | None = None,
    delivery_lon: Decimal | str | int | float | None = None,
    delivery_zone_code: str = "",
    delivery_zone_name: str = "",
    delivery_fee: Decimal | str | int | float | None = None,
    promo_code: str = "",
    promo_discount_amount: Decimal | str | int | float | None = None,
    cart_snapshot: list[dict] | None = None,
) -> Order:
    cart_snapshot = cart_snapshot or []
    delivery_fee_amount = _money(delivery_fee)
    promo_discount = _money(promo_discount_amount)

    with transaction.atomic():
        order = Order.objects.create(
            status=Order.Status.NEW,
            fulfillment=fulfillment,
            payment_method=payment_method,
            customer_name=(customer_name or "").strip(),
            customer_phone=(customer_phone or "").strip(),
            customer_comment=(customer_comment or "").strip(),
            address_line=(address_line or "").strip(),
            address_entrance=(address_entrance or "").strip(),
            address_floor=(address_floor or "").strip(),
            address_apartment=(address_apartment or "").strip(),
            delivery_lat=_coord(delivery_lat),
            delivery_lon=_coord(delivery_lon),
            delivery_zone_code=(delivery_zone_code or "").strip(),
            delivery_zone_name=(delivery_zone_name or "").strip(),
            delivery_fee=delivery_fee_amount,
            promo_code=(promo_code or "").strip(),
            promo_discount_amount=promo_discount,
            total=ZERO_AMOUNT,
        )

        subtotal = ZERO_AMOUNT

        for item in cart_snapshot:
            kind = item.get("kind")
            quantity = int(item.get("quantity") or 0)
            if quantity <= 0:
                continue

            unit_price = _money(item.get("unit_price"))
            line_total = _money(item.get("line_total")) or (unit_price * quantity)

            product = None
            lunch_day = None
            if kind == "product":
                product_id = item.get("product_id")
                if product_id:
                    product = Product.objects.filter(id=product_id).first()
            elif kind == "business_lunch":
                lunch_day_id = item.get("lunch_day_id")
                if lunch_day_id:
                    lunch_day = BusinessLunchDay.objects.filter(id=lunch_day_id).first()
            else:
                continue

            OrderItem.objects.create(
                order=order,
                product=product,
                lunch_day=lunch_day,
                product_name=(item.get("product_name") or "").strip(),
                unit_price=unit_price,
                quantity=quantity,
                line_total=line_total,
            )
            subtotal += line_total

        order.total = (max(ZERO_AMOUNT, subtotal - promo_discount) + delivery_fee_amount).quantize(
            Decimal("0.01")
        )
        order.save(update_fields=["total"])

    return order


def send_order_created_notification(order: Order) -> None:
    try:
        result = send_message(
            format_new_order_message(order),
            reply_markup=build_order_status_keyboard(order),
        )

        telegram_result = (result or {}).get("result") or {}
        chat = telegram_result.get("chat") or {}
        message_id = telegram_result.get("message_id")
        chat_id = chat.get("id")

        if chat_id is not None and message_id is not None:
            order.telegram_chat_id = str(chat_id)
            order.telegram_message_id = int(message_id)
            order.save(
                update_fields=[
                    "telegram_chat_id",
                    "telegram_message_id",
                    "updated_at",
                ]
            )
    except TelegramError as exc:
        logger.exception("Telegram notification failed: %s", exc)


def sync_online_payment_attempt(
    attempt: OnlinePaymentAttempt,
    payment_payload: dict,
) -> tuple[OnlinePaymentAttempt, Order | None]:
    provider_status = (payment_payload or {}).get("status", "").strip()
    mapped_status = {
        "succeeded": OnlinePaymentAttempt.Status.SUCCEEDED,
        "canceled": OnlinePaymentAttempt.Status.CANCELED,
    }.get(provider_status, OnlinePaymentAttempt.Status.PENDING)

    with transaction.atomic():
        locked_attempt = OnlinePaymentAttempt.objects.select_for_update().get(pk=attempt.pk)

        fields_to_update = [
            "provider_status",
            "provider_payload",
            "status",
            "updated_at",
        ]
        locked_attempt.provider_status = provider_status
        locked_attempt.provider_payload = payment_payload or {}
        locked_attempt.status = mapped_status

        if locked_attempt.order_id:
            locked_attempt.save(update_fields=fields_to_update)
            return locked_attempt, locked_attempt.order

        order = None
        if provider_status == "succeeded":
            order = create_order_from_snapshot(
                fulfillment=locked_attempt.fulfillment,
                payment_method=locked_attempt.payment_method,
                customer_name=locked_attempt.customer_name,
                customer_phone=locked_attempt.customer_phone,
                customer_comment=locked_attempt.customer_comment,
                address_line=locked_attempt.address_line,
                address_entrance=locked_attempt.address_entrance,
                address_floor=locked_attempt.address_floor,
                address_apartment=locked_attempt.address_apartment,
                delivery_lat=locked_attempt.delivery_lat,
                delivery_lon=locked_attempt.delivery_lon,
                delivery_zone_code=locked_attempt.delivery_zone_code,
                delivery_zone_name=locked_attempt.delivery_zone_name,
                delivery_fee=locked_attempt.delivery_fee,
                promo_code=locked_attempt.promo_code,
                promo_discount_amount=locked_attempt.promo_discount_amount,
                cart_snapshot=locked_attempt.cart_snapshot,
            )
            locked_attempt.order = order
            fields_to_update.append("order")

        locked_attempt.save(update_fields=fields_to_update)

    if order:
        send_order_created_notification(order)

    return locked_attempt, order


def sync_order_telegram_message(order: Order) -> bool:
    """
    Обновляет Telegram-сообщение, связанное с заказом.
    Возвращает True, если попытка обновления была успешной.
    Возвращает False, если у заказа нет сохранённых telegram ids.
    Исключения TelegramError не пробрасываются наружу.
    """
    if not order.telegram_chat_id or not order.telegram_message_id:
        return False

    try:
        edit_message_text(
            chat_id=order.telegram_chat_id,
            message_id=order.telegram_message_id,
            text=format_new_order_message(order),
            reply_markup=build_order_status_keyboard(order),
        )
        return True
    except TelegramError:
        logger.exception("Failed to sync telegram message for order %s", order.id)
        return False
