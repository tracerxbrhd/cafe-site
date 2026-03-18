# from django.http import JsonResponse
# from django.views.decorators.http import require_POST, require_http_methods

# import logging
# from decimal import Decimal
# from django.shortcuts import get_object_or_404, redirect, render
# from core.models import BusinessLunchDay
# from catalog.models import Product
# from .forms import CheckoutForm
# from .models import Order, OrderItem

# from integrations.telegram.client import send_message, TelegramError
# from .notifications import format_new_order_message, build_order_status_keyboard

# from core.utils import get_cafe_settings, get_delivery_quote
# from django.contrib import messages

# from .cart import _get_cart_dict, cart_get_qty  # добавь импорт (или сделай отдельную функцию cart_get_qty)

# from .cart import (
#     add_business_lunch,
#     cart_add,
#     cart_clear,
#     cart_count,
#     cart_lines,
#     cart_set,
# )
from decimal import Decimal

from django.contrib import messages
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST, require_http_methods

from core.models import BusinessLunchDay
from core.utils import (
    get_active_delivery_zones_map_data,
    get_cafe_settings,
    get_delivery_quote,
)
from promotions.services import PromoCodeError, apply_promo_code

from .cart import (
    add_business_lunch,
    cart_add,
    cart_clear,
    cart_count,
    cart_get_qty,
    cart_lines,
    cart_set,
)
from .forms import CheckoutForm, OrderLookupPhoneForm, OrderLookupPublicIdForm
from .models import OnlinePaymentAttempt, Order
from .services import (
    create_order_from_snapshot,
    send_order_created_notification,
    serialize_cart_lines,
    sync_online_payment_attempt,
)
from .yookassa import (
    YooKassaConfigurationError,
    YooKassaError,
    create_payment as create_yookassa_payment,
    get_payment as get_yookassa_payment,
    is_yookassa_configured,
)


ZERO_AMOUNT = Decimal("0.00")


def _discounted_items_total(items_total: Decimal, promo_discount: Decimal) -> Decimal:
    return max(ZERO_AMOUNT, items_total - promo_discount).quantize(Decimal("0.01"))


def _checkout_grand_total(
    items_total: Decimal,
    promo_discount: Decimal,
    delivery_fee: Decimal,
) -> Decimal:
    return (_discounted_items_total(items_total, promo_discount) + delivery_fee).quantize(
        Decimal("0.01")
    )


def _resolve_promo_discount(form: CheckoutForm, items_total: Decimal) -> tuple[str, Decimal, str]:
    promo_code = (form.cleaned_data.get("promo_code") or "").strip()
    if not promo_code:
        return "", ZERO_AMOUNT, ""

    try:
        result = apply_promo_code(promo_code, items_total)
    except PromoCodeError as exc:
        form.add_error("promo_code", str(exc))
        return "", ZERO_AMOUNT, ""

    return result.code, result.discount_amount, result.discount_label


def _create_order_from_checkout(
    *,
    lines,
    fulfillment: str,
    payment_method: str,
    customer_name: str,
    customer_phone: str,
    customer_comment: str,
    address_line: str,
    address_entrance: str,
    address_floor: str,
    address_apartment: str,
    delivery_lat,
    delivery_lon,
    delivery_zone_code: str,
    delivery_zone_name: str,
    delivery_fee: Decimal,
    promo_code: str,
    promo_discount: Decimal,
):
    order = create_order_from_snapshot(
        fulfillment=fulfillment,
        payment_method=payment_method,
        customer_name=customer_name,
        customer_phone=customer_phone,
        customer_comment=customer_comment,
        address_line=address_line,
        address_entrance=address_entrance,
        address_floor=address_floor,
        address_apartment=address_apartment,
        delivery_lat=delivery_lat,
        delivery_lon=delivery_lon,
        delivery_zone_code=delivery_zone_code,
        delivery_zone_name=delivery_zone_name,
        delivery_fee=delivery_fee,
        promo_code=promo_code,
        promo_discount_amount=promo_discount,
        cart_snapshot=serialize_cart_lines(lines),
    )
    send_order_created_notification(order)
    return order


def _create_online_payment_attempt(
    *,
    lines,
    items_total: Decimal,
    fulfillment: str,
    payment_method: str,
    customer_name: str,
    customer_phone: str,
    customer_comment: str,
    address_line: str,
    address_entrance: str,
    address_floor: str,
    address_apartment: str,
    delivery_lat,
    delivery_lon,
    delivery_zone_code: str,
    delivery_zone_name: str,
    delivery_fee: Decimal,
    promo_code: str,
    promo_discount: Decimal,
    grand_total: Decimal,
):
    return OnlinePaymentAttempt.objects.create(
        fulfillment=fulfillment,
        payment_method=payment_method,
        customer_name=customer_name,
        customer_phone=customer_phone,
        customer_comment=customer_comment,
        address_line=address_line,
        address_entrance=address_entrance,
        address_floor=address_floor,
        address_apartment=address_apartment,
        delivery_lat=Decimal(str(delivery_lat)).quantize(Decimal("0.000001"))
        if delivery_lat is not None
        else None,
        delivery_lon=Decimal(str(delivery_lon)).quantize(Decimal("0.000001"))
        if delivery_lon is not None
        else None,
        delivery_zone_code=delivery_zone_code,
        delivery_zone_name=delivery_zone_name,
        items_total=items_total,
        delivery_fee=delivery_fee,
        promo_code=promo_code,
        promo_discount_amount=promo_discount,
        total=grand_total,
        cart_snapshot=serialize_cart_lines(lines),
    )


def _sync_attempt_from_provider(attempt: OnlinePaymentAttempt):
    if not attempt.payment_id:
        return attempt, None

    payment = get_yookassa_payment(attempt.payment_id)
    return sync_online_payment_attempt(attempt, payment.raw)


def _clear_cart_for_attempt_if_unchanged(request, attempt: OnlinePaymentAttempt) -> None:
    current_lines, _ = cart_lines(request.session)
    if serialize_cart_lines(current_lines) == (attempt.cart_snapshot or []):
        cart_clear(request.session)


def cart_page(request):
    lines, total = cart_lines(request.session)
    return render(request, "orders/cart.html", {"lines": lines, "total": total})


def order_lookup_page(request):
    phone_form = OrderLookupPhoneForm()
    public_id_form = OrderLookupPublicIdForm()

    lookup_mode = (request.GET.get("lookup") or "").strip()
    if not lookup_mode:
        if (request.GET.get("public_id") or "").strip():
            lookup_mode = "public_id"
        elif (request.GET.get("phone") or "").strip():
            lookup_mode = "phone"

    public_id_order = None
    phone_orders = []
    active_phone_orders = []
    completed_phone_orders = []
    searched_phone = ""
    public_id_lookup_done = False
    phone_lookup_done = False

    if lookup_mode == "public_id":
        public_id_lookup_done = True
        public_id_form = OrderLookupPublicIdForm(request.GET)
        if public_id_form.is_valid():
            public_id_order = (
                Order.objects.filter(public_id=public_id_form.cleaned_data["public_id"])
                .prefetch_related("items")
                .first()
            )
    elif lookup_mode == "phone":
        phone_lookup_done = True
        phone_form = OrderLookupPhoneForm(request.GET)
        if phone_form.is_valid():
            searched_phone = phone_form.cleaned_data["phone"]
            phone_orders = list(
                Order.objects.filter(customer_phone=searched_phone)
                .order_by("-created_at")
                .prefetch_related("items")
            )
            terminal_statuses = {Order.Status.DONE, Order.Status.CANCELED}
            active_phone_orders = [o for o in phone_orders if o.status not in terminal_statuses]
            completed_phone_orders = [o for o in phone_orders if o.status in terminal_statuses]

    return render(
        request,
        "orders/order_lookup.html",
        {
            "lookup_mode": lookup_mode,
            "phone_form": phone_form,
            "public_id_form": public_id_form,
            "public_id_order": public_id_order,
            "public_id_lookup_done": public_id_lookup_done,
            "searched_phone": searched_phone,
            "phone_orders": phone_orders,
            "active_phone_orders": active_phone_orders,
            "completed_phone_orders": completed_phone_orders,
            "phone_lookup_done": phone_lookup_done,
        },
    )


# def cart_api_summary(request):
#     lines, total = cart_lines(request.session)
#     return JsonResponse(
#         {
#             "count": cart_count(request.session),
#             "total": str(total),
#             "items": [
#                 {
#                     "product_id": line.product.id,
#                     "qty": line.qty,
#                     "line_total": str(line.line_total),
#                 }
#                 for line in lines
#             ],
#         }
#     )
def cart_api_summary(request):
    lines, total = cart_lines(request.session)

    items = []
    for line in lines:
        if line.kind == "product" and line.product:
            items.append(
                {
                    "kind": "product",
                    "product_id": line.product.id,
                    "qty": line.qty,
                    "line_total": str(line.line_total),
                }
            )
        elif line.kind == "business_lunch" and line.lunch_day:
            items.append(
                {
                    "kind": "business_lunch",
                    "lunch_day_id": line.lunch_day.id,
                    "qty": line.qty,
                    "line_total": str(line.line_total),
                }
            )

    return JsonResponse(
        {
            "count": cart_count(request.session),
            "total": str(total),
            "items": items,
        }
    )


@require_POST
def cart_api_add(request):
    product_id = int(request.POST.get("product_id", "0"))
    qty_delta = int(request.POST.get("qty_delta", "1"))
    cart_add(request.session, product_id=product_id, qty_delta=qty_delta)
    return JsonResponse({"ok": True, "count": cart_count(request.session), "product_id": product_id, "qty": cart_get_qty(request.session, product_id)})


@require_POST
def cart_api_set(request):
    product_id = int(request.POST.get("product_id", "0"))
    qty = int(request.POST.get("qty", "0"))
    cart_set(request.session, product_id=product_id, qty=qty)
    return JsonResponse(
        {
            "ok": True,
            "count": cart_count(request.session),
            "product_id": product_id,
            "qty": cart_get_qty(request.session, product_id),
        }
    )


@require_POST
def cart_api_clear(request):
    cart_clear(request.session)
    return JsonResponse({"ok": True, "count": 0})


# @require_http_methods(["GET", "POST"])
# def checkout_page(request):
#     lines, items_total = cart_lines(request.session)
#     if not lines:
#         return redirect("orders:cart")

#     cafe_settings = get_cafe_settings()

#     if cafe_settings:
#         if not cafe_settings.is_currently_open():
#             messages.error(
#                 request,
#                 f"Сейчас приём заказов недоступен. Режим работы: {cafe_settings.working_hours_text}."
#             )
#             return redirect("orders:cart")

#     if request.method == "POST":
#         form = CheckoutForm(request.POST)
#         if form.is_valid():
#             fulfillment = form.cleaned_data["fulfillment"]

#             delivery_fee = Decimal("0.00")
#             min_order_amount = cafe_settings.min_order_amount if cafe_settings else Decimal("0.00")

#             if fulfillment == Order.Fulfillment.DELIVERY:
#                 lat = float(form.cleaned_data["delivery_lat"])
#                 lon = float(form.cleaned_data["delivery_lon"])
#                 quote = get_delivery_quote(lat=lat, lon=lon, fulfillment=fulfillment)

#                 if not quote.is_deliverable:
#                     form.add_error("address_line", quote.reason or "Адрес вне зоны доставки.")
#                 else:
#                     delivery_fee = quote.delivery_fee
#                     min_order_amount = quote.min_order_amount
#             else:
#                 quote = None

#             grand_total = items_total + delivery_fee

#             if not form.errors:
#                 if grand_total < min_order_amount:
#                     form.add_error(
#                         None,
#                         f"Минимальная сумма заказа: {min_order_amount} ₽."
#                     )
#                 else:
#                     order = Order.objects.create(
#                         status=Order.Status.NEW,
#                         fulfillment=fulfillment,
#                         customer_name=form.cleaned_data["customer_name"],
#                         customer_phone=form.cleaned_data["customer_phone"],
#                         customer_comment=form.cleaned_data.get("customer_comment", "") or "",
#                         address_line=form.cleaned_data.get("address_line", "") or "",
#                         address_entrance=form.cleaned_data.get("address_entrance", "") or "",
#                         address_floor=form.cleaned_data.get("address_floor", "") or "",
#                         address_apartment=form.cleaned_data.get("address_apartment", "") or "",
#                         total=Decimal("0.00"),
#                     )

#                     order_total = Decimal("0.00")
#                     for line in lines:
#                         item = OrderItem.objects.create(
#                             order=order,
#                             product=line.product,
#                             product_name=line.product.name,
#                             unit_price=line.product.price,
#                             quantity=line.qty,
#                             line_total=line.line_total,
#                         )
#                         order_total += item.line_total

#                     order_total += delivery_fee
#                     order.total = order_total.quantize(Decimal("0.01"))
#                     order.save(update_fields=["total"])


#             logger = logging.getLogger(__name__)


#             try:
#                 result = send_message(
#                     format_new_order_message(order),
#                     reply_markup=build_order_status_keyboard(order),
#                 )

#                 telegram_result = (result or {}).get("result") or {}
#                 chat = telegram_result.get("chat") or {}
#                 message_id = telegram_result.get("message_id")

#                 chat_id = chat.get("id")
#                 if chat_id is not None and message_id is not None:
#                     order.telegram_chat_id = str(chat_id)
#                     order.telegram_message_id = int(message_id)
#                     order.save(update_fields=["telegram_chat_id", "telegram_message_id", "updated_at"])
#             except TelegramError as e:
#                 # В MVP не ломаем заказ из-за Telegram
#                 logger.exception("Telegram notification failed: %s", e)

#             cart_clear(request.session)
#             # return redirect("orders:order_status", public_id=order.public_id)
#             return redirect("orders:order_success", public_id=order.public_id)
#     else:
#         form = CheckoutForm()


#     selected_fulfillment = (
#         form.data.get("fulfillment")
#         if request.method == "POST"
#         else Order.Fulfillment.DELIVERY
#     )

#     delivery_fee = get_delivery_fee(selected_fulfillment)
#     grand_total = items_total + delivery_fee


#     selected_fulfillment = (
#         form.data.get("fulfillment")
#         if request.method == "POST"
#         else Order.Fulfillment.DELIVERY
#     )

#     delivery_fee = Decimal("0.00")
#     grand_total = items_total

#     if selected_fulfillment == Order.Fulfillment.DELIVERY and request.method == "POST":
#         try:
#             lat = float((form.data.get("delivery_lat") or "").strip())
#             lon = float((form.data.get("delivery_lon") or "").strip())
#             quote = get_delivery_quote(lat=lat, lon=lon, fulfillment=selected_fulfillment)
#             if quote.is_deliverable:
#                 delivery_fee = quote.delivery_fee
#                 grand_total = items_total + delivery_fee
#         except Exception:
#             pass

#     # return render(request, "orders/checkout.html", {"form": form, "lines": lines, "total": total})
#     return render(
#         request,
#         "orders/checkout.html",
#         {
#             "form": form,
#             "lines": lines,
#             "items_total": items_total,
#             "delivery_fee": delivery_fee,
#             "grand_total": grand_total,
#         },
#     )
# @require_http_methods(["GET", "POST"])
# def checkout_page(request):
#     lines, items_total = cart_lines(request.session)
#     if not lines:
#         return redirect("orders:cart")

#     cafe_settings = get_cafe_settings()

#     if cafe_settings:
#         if not cafe_settings.is_currently_open():
#             messages.error(
#                 request,
#                 f"Сейчас приём заказов недоступен. Режим работы: {cafe_settings.working_hours_text}."
#             )
#             return redirect("orders:cart")

#     form = CheckoutForm(request.POST or None)

#     if request.method == "POST":
#         if form.is_valid():
#             fulfillment = form.cleaned_data["fulfillment"]

#             delivery_fee = Decimal("0.00")
#             min_order_amount = cafe_settings.min_order_amount if cafe_settings else Decimal("0.00")

#             if fulfillment == Order.Fulfillment.DELIVERY:
#                 lat = float(form.cleaned_data["delivery_lat"])
#                 lon = float(form.cleaned_data["delivery_lon"])
#                 quote = get_delivery_quote(lat=lat, lon=lon, fulfillment=fulfillment)

#                 if not quote.is_deliverable:
#                     form.add_error("address_line", quote.reason or "Адрес вне зоны доставки.")
#                 else:
#                     delivery_fee = quote.delivery_fee
#                     min_order_amount = quote.min_order_amount
#             else:
#                 quote = None

#             grand_total = items_total + delivery_fee

#             if not form.errors:
#                 if grand_total < min_order_amount:
#                     form.add_error(
#                         None,
#                         f"Минимальная сумма заказа: {min_order_amount} ₽."
#                     )
#                 else:
#                     order = Order.objects.create(
#                         status=Order.Status.NEW,
#                         fulfillment=fulfillment,
#                         customer_name=form.cleaned_data["customer_name"],
#                         customer_phone=form.cleaned_data["customer_phone"],
#                         customer_comment=form.cleaned_data.get("customer_comment", "") or "",
#                         address_line=form.cleaned_data.get("address_line", "") or "",
#                         address_entrance=form.cleaned_data.get("address_entrance", "") or "",
#                         address_floor=form.cleaned_data.get("address_floor", "") or "",
#                         address_apartment=form.cleaned_data.get("address_apartment", "") or "",
#                         total=Decimal("0.00"),
#                     )

#                     order_total = Decimal("0.00")
#                     for line in lines:
#                         item = OrderItem.objects.create(
#                             order=order,
#                             product=line.product,
#                             product_name=line.product.name,
#                             unit_price=line.product.price,
#                             quantity=line.qty,
#                             line_total=line.line_total,
#                         )
#                         order_total += item.line_total

#                     order_total += delivery_fee
#                     order.total = order_total.quantize(Decimal("0.01"))
#                     order.save(update_fields=["total"])

#                     logger = logging.getLogger(__name__)

#                     try:
#                         result = send_message(
#                             format_new_order_message(order),
#                             reply_markup=build_order_status_keyboard(order),
#                         )

#                         telegram_result = (result or {}).get("result") or {}
#                         chat = telegram_result.get("chat") or {}
#                         message_id = telegram_result.get("message_id")

#                         chat_id = chat.get("id")
#                         if chat_id is not None and message_id is not None:
#                             order.telegram_chat_id = str(chat_id)
#                             order.telegram_message_id = int(message_id)
#                             order.save(update_fields=["telegram_chat_id", "telegram_message_id", "updated_at"])

#                     except TelegramError as e:
#                         logger.exception("Telegram notification failed: %s", e)

#                     cart_clear(request.session)
#                     return redirect("orders:order_success", public_id=order.public_id)

#     selected_fulfillment = (
#         form.data.get("fulfillment")
#         if request.method == "POST"
#         else Order.Fulfillment.DELIVERY
#     )

#     delivery_fee = Decimal("0.00")
#     grand_total = items_total

#     if selected_fulfillment == Order.Fulfillment.DELIVERY and request.method == "POST":
#         try:
#             lat = float((form.data.get("delivery_lat") or "").strip())
#             lon = float((form.data.get("delivery_lon") or "").strip())
#             quote = get_delivery_quote(lat=lat, lon=lon, fulfillment=selected_fulfillment)
#             if quote.is_deliverable:
#                 delivery_fee = quote.delivery_fee
#                 grand_total = items_total + delivery_fee
#         except Exception:
#             pass

#     return render(
#         request,
#         "orders/checkout.html",
#         {
#             "form": form,
#             "lines": lines,
#             "items_total": items_total,
#             "delivery_fee": delivery_fee,
#             "grand_total": grand_total,
#         },
#     )
@require_http_methods(["GET", "POST"])
def checkout_page(request):
    lines, items_total = cart_lines(request.session)
    if not lines:
        return redirect("orders:cart")

    cafe_settings = get_cafe_settings()

    if cafe_settings and not cafe_settings.is_accepting_orders_now():
        messages.error(
            request,
            f"Сейчас приём заказов недоступен. Приём заказов: {cafe_settings.order_hours_display}."
        )
        return redirect("orders:cart")

    form = CheckoutForm(request.POST or None)

    delivery_fee = ZERO_AMOUNT
    promo_discount = ZERO_AMOUNT
    applied_promo_code = ""
    promo_discount_label = ""
    grand_total = items_total

    if request.method == "POST":
        form.is_valid()

        applied_promo_code, promo_discount, promo_discount_label = _resolve_promo_discount(
            form, items_total
        )

        fulfillment = form.cleaned_data.get("fulfillment")
        min_order_amount = cafe_settings.min_order_amount if cafe_settings else ZERO_AMOUNT

        quote = None
        delivery_lat = None
        delivery_lon = None

        if fulfillment == Order.Fulfillment.DELIVERY:
            try:
                delivery_lat = float(form.cleaned_data["delivery_lat"])
                delivery_lon = float(form.cleaned_data["delivery_lon"])
                quote = get_delivery_quote(
                    lat=delivery_lat,
                    lon=delivery_lon,
                    fulfillment=fulfillment,
                )

                if not quote.is_deliverable:
                    form.add_error(
                        "address_line",
                        quote.reason or "Адрес вне зоны доставки."
                    )
                else:
                    delivery_fee = quote.delivery_fee
                    min_order_amount = quote.min_order_amount
            except Exception:
                delivery_fee = ZERO_AMOUNT
        else:
            delivery_fee = ZERO_AMOUNT

        grand_total = _checkout_grand_total(items_total, promo_discount, delivery_fee)

        if not form.errors and items_total < min_order_amount:
            form.add_error(
                None,
                f"Минимальная сумма заказа: {min_order_amount} ₽."
            )

        if not form.errors:
            payment_method = form.cleaned_data["payment_method"]

            if payment_method == Order.PaymentMethod.ONLINE:
                if not is_yookassa_configured():
                    form.add_error(
                        None,
                        "Онлайн-оплата пока не настроена. Добавьте тестовые ключи ЮKassa в .env.",
                    )
                else:
                    attempt = _create_online_payment_attempt(
                        lines=lines,
                        items_total=items_total,
                        fulfillment=fulfillment,
                        payment_method=payment_method,
                        customer_name=form.cleaned_data["customer_name"],
                        customer_phone=form.cleaned_data["customer_phone"],
                        customer_comment=form.cleaned_data.get("customer_comment", "") or "",
                        address_line=form.cleaned_data.get("address_line", "") or "",
                        address_entrance=form.cleaned_data.get("address_entrance", "") or "",
                        address_floor=form.cleaned_data.get("address_floor", "") or "",
                        address_apartment=form.cleaned_data.get("address_apartment", "") or "",
                        delivery_lat=delivery_lat,
                        delivery_lon=delivery_lon,
                        delivery_zone_code=quote.zone.code if quote and quote.zone else "",
                        delivery_zone_name=quote.zone.name if quote and quote.zone else "",
                        delivery_fee=delivery_fee,
                        promo_code=applied_promo_code,
                        promo_discount=promo_discount,
                        grand_total=grand_total,
                    )
                    return_url = request.build_absolute_uri(
                        reverse("orders:payment_return", kwargs={"public_id": attempt.public_id})
                    )

                    try:
                        payment = create_yookassa_payment(
                            amount=grand_total,
                            description=f"Заказ в кафе Сказка ({attempt.customer_phone})",
                            return_url=return_url,
                            idempotence_key=str(attempt.idempotence_key),
                            metadata={
                                "payment_attempt_id": str(attempt.public_id),
                                "customer_phone": attempt.customer_phone,
                            },
                        )
                    except (YooKassaConfigurationError, YooKassaError) as exc:
                        attempt.status = OnlinePaymentAttempt.Status.FAILED
                        attempt.error_message = str(exc)
                        attempt.save(update_fields=["status", "error_message", "updated_at"])
                        form.add_error(None, str(exc))
                    else:
                        attempt.payment_id = payment.payment_id or None
                        attempt.provider_status = payment.status
                        attempt.provider_payload = payment.raw
                        attempt.confirmation_url = payment.confirmation_url
                        attempt.status = {
                            "succeeded": OnlinePaymentAttempt.Status.SUCCEEDED,
                            "canceled": OnlinePaymentAttempt.Status.CANCELED,
                        }.get(payment.status, OnlinePaymentAttempt.Status.PENDING)
                        attempt.save(
                            update_fields=[
                                "payment_id",
                                "provider_status",
                                "provider_payload",
                                "confirmation_url",
                                "status",
                                "updated_at",
                            ]
                        )
                        if payment.status == "succeeded":
                            attempt, order = sync_online_payment_attempt(attempt, payment.raw)
                            if order:
                                cart_clear(request.session)
                                return redirect("orders:order_success", public_id=order.public_id)

                        if payment.confirmation_url:
                            return redirect(payment.confirmation_url)

                        attempt.status = OnlinePaymentAttempt.Status.FAILED
                        attempt.error_message = (
                            "ЮKassa не вернула ссылку на оплату. Попробуйте ещё раз."
                        )
                        attempt.save(update_fields=["status", "error_message", "updated_at"])
                        form.add_error(None, attempt.error_message)

            if not form.errors:
                order = _create_order_from_checkout(
                    lines=lines,
                    fulfillment=fulfillment,
                    payment_method=payment_method,
                    customer_name=form.cleaned_data["customer_name"],
                    customer_phone=form.cleaned_data["customer_phone"],
                    customer_comment=form.cleaned_data.get("customer_comment", "") or "",
                    address_line=form.cleaned_data.get("address_line", "") or "",
                    address_entrance=form.cleaned_data.get("address_entrance", "") or "",
                    address_floor=form.cleaned_data.get("address_floor", "") or "",
                    address_apartment=form.cleaned_data.get("address_apartment", "") or "",
                    delivery_lat=delivery_lat,
                    delivery_lon=delivery_lon,
                    delivery_zone_code=quote.zone.code if quote and quote.zone else "",
                    delivery_zone_name=quote.zone.name if quote and quote.zone else "",
                    delivery_fee=delivery_fee,
                    promo_code=applied_promo_code,
                    promo_discount=promo_discount,
                )
                cart_clear(request.session)
                return redirect("orders:order_success", public_id=order.public_id)

    # Предварительный расчёт для отображения формы
    selected_fulfillment = (
        form.data.get("fulfillment")
        if request.method == "POST"
        else Order.Fulfillment.DELIVERY
    )

    if selected_fulfillment == Order.Fulfillment.DELIVERY and request.method == "POST":
        try:
            lat = float((form.data.get("delivery_lat") or "").strip())
            lon = float((form.data.get("delivery_lon") or "").strip())
            quote = get_delivery_quote(
                lat=lat,
                lon=lon,
                fulfillment=selected_fulfillment,
            )
            if quote.is_deliverable:
                delivery_fee = quote.delivery_fee
        except Exception:
            delivery_fee = ZERO_AMOUNT

    grand_total = _checkout_grand_total(items_total, promo_discount, delivery_fee)

    return render(
        request,
        "orders/checkout.html",
        {
            "form": form,
            "lines": lines,
            "items_total": items_total,
            "promo_discount": promo_discount,
            "applied_promo_code": applied_promo_code,
            "promo_discount_label": promo_discount_label,
            "delivery_fee": delivery_fee,
            "grand_total": grand_total,
            "online_payment_enabled": is_yookassa_configured(),
            "delivery_zones_map": get_active_delivery_zones_map_data(),
        },
    )


def order_status_page(request, public_id):
    order = get_object_or_404(Order.objects.prefetch_related("items"), public_id=public_id)
    return render(request, "orders/order_status.html", {"order": order})

def order_api_status(request, public_id):
    order = get_object_or_404(Order, public_id=public_id)
    return JsonResponse(
        {
            "status": order.status,
            "status_label": order.get_status_display(),
            "updated_at": order.updated_at.isoformat(),
            "total": str(order.total),
        }
    )


def order_success_page(request, public_id):
    order = get_object_or_404(Order, public_id=public_id)
    return render(request, "orders/order_success.html", {"order": order})


def payment_return_page(request, public_id):
    attempt = get_object_or_404(
        OnlinePaymentAttempt.objects.select_related("order"),
        public_id=public_id,
    )

    if attempt.order_id:
        _clear_cart_for_attempt_if_unchanged(request, attempt)
        return redirect("orders:order_success", public_id=attempt.order.public_id)

    payment_error = ""
    if attempt.payment_id:
        try:
            attempt, order = _sync_attempt_from_provider(attempt)
        except YooKassaError as exc:
            payment_error = str(exc)
            order = None
        else:
            if order:
                _clear_cart_for_attempt_if_unchanged(request, attempt)
                return redirect("orders:order_success", public_id=order.public_id)
    else:
        order = None
        payment_error = attempt.error_message or "Платёж ЮKassa ещё не создан."

    return render(
        request,
        "orders/payment_return.html",
        {
            "attempt": attempt,
            "payment_error": payment_error,
            "is_terminal": attempt.status in {
                OnlinePaymentAttempt.Status.SUCCEEDED,
                OnlinePaymentAttempt.Status.CANCELED,
                OnlinePaymentAttempt.Status.FAILED,
            },
        },
    )


def payment_api_status(request, public_id):
    attempt = get_object_or_404(
        OnlinePaymentAttempt.objects.select_related("order"),
        public_id=public_id,
    )

    if attempt.order_id:
        _clear_cart_for_attempt_if_unchanged(request, attempt)
        return JsonResponse(
            {
                "ok": True,
                "status": attempt.status,
                "status_label": attempt.get_status_display(),
                "is_terminal": True,
                "redirect_url": reverse(
                    "orders:order_success",
                    kwargs={"public_id": attempt.order.public_id},
                ),
            }
        )

    if not attempt.payment_id:
        return JsonResponse(
            {
                "ok": False,
                "status": attempt.status,
                "status_label": attempt.get_status_display(),
                "is_terminal": attempt.status
                in {
                    OnlinePaymentAttempt.Status.CANCELED,
                    OnlinePaymentAttempt.Status.FAILED,
                },
                "error": attempt.error_message or "Платёж ЮKassa не найден.",
            },
            status=400,
        )

    try:
        attempt, order = _sync_attempt_from_provider(attempt)
    except YooKassaError as exc:
        return JsonResponse(
            {
                "ok": False,
                "status": attempt.status,
                "status_label": attempt.get_status_display(),
                "is_terminal": False,
                "error": str(exc),
            },
            status=502,
        )

    payload = {
        "ok": True,
        "status": attempt.status,
        "status_label": attempt.get_status_display(),
        "is_terminal": attempt.status
        in {
            OnlinePaymentAttempt.Status.SUCCEEDED,
            OnlinePaymentAttempt.Status.CANCELED,
            OnlinePaymentAttempt.Status.FAILED,
        },
        "redirect_url": "",
        "error": attempt.error_message,
    }

    if order:
        _clear_cart_for_attempt_if_unchanged(request, attempt)
        payload["redirect_url"] = reverse(
            "orders:order_success",
            kwargs={"public_id": order.public_id},
        )

    return JsonResponse(payload)


@require_POST
def checkout_api_apply_promo(request):
    lines, items_total = cart_lines(request.session)
    if not lines:
        return JsonResponse({"ok": False, "error": "Корзина пуста."}, status=400)

    raw_promo_code = request.POST.get("promo_code", "")
    if not raw_promo_code.strip():
        return JsonResponse(
            {
                "ok": True,
                "promo_code": "",
                "discount_amount": "0.00",
                "discount_label": "",
                "discounted_items_total": str(items_total.quantize(Decimal("0.01"))),
                "message": "Промокод сброшен.",
            }
        )

    try:
        result = apply_promo_code(raw_promo_code, items_total)
    except PromoCodeError as exc:
        return JsonResponse({"ok": False, "error": str(exc)}, status=400)

    return JsonResponse(
        {
            "ok": True,
            "promo_code": result.code,
            "discount_amount": str(result.discount_amount),
            "discount_label": result.discount_label,
            "discounted_items_total": str(
                _discounted_items_total(items_total, result.discount_amount)
            ),
            "message": "Промокод применён.",
        }
    )


@require_POST
def delivery_api_quote(request):
    try:
        lat = float(request.POST.get("lat", "").strip())
        lon = float(request.POST.get("lon", "").strip())
    except Exception:
        return JsonResponse({"ok": False, "error": "Некорректные координаты"}, status=400)

    fulfillment = (request.POST.get("fulfillment") or "delivery").strip()
    quote = get_delivery_quote(lat=lat, lon=lon, fulfillment=fulfillment)

    return JsonResponse(
        {
            "ok": True,
            "is_deliverable": quote.is_deliverable,
            "zone_code": quote.zone.code if quote.zone else "",
            "zone_name": quote.zone.name if quote.zone else "",
            "delivery_fee": str(quote.delivery_fee),
            "min_order_amount": str(quote.min_order_amount),
            "reason": quote.reason,
        }
    )



@require_POST
def cart_api_add_business_lunch(request):
    try:
        lunch_day_id = int(request.POST.get("lunch_day_id", "0"))
        qty_delta = int(request.POST.get("qty_delta", "1"))
    except ValueError:
        return JsonResponse({"ok": False, "error": "Некорректные параметры"}, status=400)

    lunch_day = BusinessLunchDay.objects.filter(id=lunch_day_id, is_active=True).first()
    if not lunch_day:
        return JsonResponse({"ok": False, "error": "Бизнес-ланч не найден"}, status=404)

    qty = add_business_lunch(request.session, lunch_day_id=lunch_day_id, qty_delta=qty_delta)

    return JsonResponse(
        {
            "ok": True,
            "kind": "business_lunch",
            "lunch_day_id": lunch_day.id,
            "qty": qty,
            "count": cart_count(request.session),
        }
    )
