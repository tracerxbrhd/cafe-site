from __future__ import annotations

from django.urls import reverse

from .models import Order


def format_new_order_message(order: Order) -> str:
    lines = []
    lines.append(f"<b>Новый заказ</b> №{order.id}")
    lines.append(f"<b>Статус:</b> {order.get_status_display()}")
    lines.append(f"<b>Способ:</b> {order.get_fulfillment_display()}")
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
        if extra:
            addr = f"{addr} ({', '.join(extra)})"
        lines.append(f"<b>Адрес:</b> {addr}")

    if order.customer_comment:
        lines.append(f"<b>Комментарий:</b> {order.customer_comment}")

    lines.append("")
    lines.append("<b>Состав:</b>")
    for it in order.items.all():
        lines.append(f"• {it.product_name} × {it.quantity} = {it.line_total} ₽")

    lines.append("")
    lines.append(f"<b>Итого:</b> {order.total} ₽")

    return "\n".join(lines)