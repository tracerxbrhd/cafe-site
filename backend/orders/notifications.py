from __future__ import annotations

from .models import Order


STATUS_BUTTONS = {
    Order.Status.CONFIRMED: "Подтвердить",
    Order.Status.COOKING: "Готовится",
    Order.Status.ON_THE_WAY: "В пути",
    Order.Status.DONE: "Выполнен",
    Order.Status.CANCELED: "Отменить",
}


def build_order_status_keyboard(order: Order) -> dict | None:
    allowed = list(order.allowed_next_statuses())
    if not allowed:
        return None

    rows = []
    current_row = []

    ordered_statuses = [
        Order.Status.CONFIRMED,
        Order.Status.COOKING,
        Order.Status.ON_THE_WAY,
        Order.Status.DONE,
        Order.Status.CANCELED,
    ]

    for status in ordered_statuses:
        if status not in allowed:
            continue

        current_row.append({
            "text": STATUS_BUTTONS[status],
            "callback_data": f"order:{order.id}:status:{status}",
        })

        if len(current_row) == 2:
            rows.append(current_row)
            current_row = []

    if current_row:
        rows.append(current_row)

    return {"inline_keyboard": rows}


def format_new_order_message(order: Order) -> str:
    lines = []
    lines.append(f"<b>Заказ №{order.id}</b>")
    lines.append(f"<b>Статус:</b> {order.get_status_display()}")
    lines.append(f"<b>Способ:</b> {order.get_fulfillment_display()}")
    lines.append(f"<b>Оплата:</b> {order.get_payment_method_display()}")
    lines.append(f"<b>Имя:</b> {order.customer_name}")
    lines.append(f"<b>Телефон:</b> {order.customer_phone}")

    if order.fulfillment == Order.Fulfillment.DELIVERY:
        addr = order.address_line or "-"
        extra = []
        if order.address_entrance:
            extra.append(f"подъезд {order.address_entrance}")
        if order.address_floor:
            extra.append(f"этаж {order.address_floor}")
        if order.address_apartment:
            extra.append(f"кв/офис {order.address_apartment}")
        if order.delivery_zone_name:
            lines.append(f"<b>Зона доставки:</b> {order.delivery_zone_name}")
        if order.delivery_fee:
            lines.append(f"<b>Доставка:</b> {order.delivery_fee} ₽")
        if extra:
            addr = f"{addr} ({', '.join(extra)})"
        lines.append(f"<b>Адрес:</b> {addr}")

    if order.customer_comment:
        lines.append(f"<b>Комментарий:</b> {order.customer_comment}")

    if order.promo_code and order.promo_discount_amount:
        lines.append(f"<b>Промокод:</b> {order.promo_code} (-{order.promo_discount_amount} ₽)")

    lines.append("")
    lines.append("<b>Состав:</b>")
    for it in order.items.all():
        lines.append(f"• {it.product_name} × {it.quantity} = {it.line_total} ₽")

    lines.append("")
    lines.append(f"<b>Итого:</b> {order.total} ₽")

    return "\n".join(lines)
