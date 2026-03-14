from __future__ import annotations

import logging

from integrations.telegram.client import TelegramError, answer_callback_query

from .models import Order
from .services import sync_order_telegram_message

logger = logging.getLogger(__name__)


ALLOWED_STATUS_TRANSITIONS = {
    "confirmed": Order.Status.CONFIRMED,
    "cooking": Order.Status.COOKING,
    "on_the_way": Order.Status.ON_THE_WAY,
    "done": Order.Status.DONE,
    "canceled": Order.Status.CANCELED,
}


def parse_callback_data(data: str):
    parts = (data or "").split(":")
    if len(parts) != 4:
        return None
    if parts[0] != "order" or parts[2] != "status":
        return None

    try:
        order_id = int(parts[1])
    except ValueError:
        return None

    status_code = parts[3]
    if status_code not in ALLOWED_STATUS_TRANSITIONS:
        return None

    return order_id, status_code


def process_telegram_update(payload: dict) -> bool:
    callback_query = payload.get("callback_query")
    if not callback_query:
        return False

    callback_query_id = callback_query.get("id")
    data = callback_query.get("data") or ""
    message = callback_query.get("message") or {}

    parsed = parse_callback_data(data)
    if not parsed:
        try:
            if callback_query_id:
                answer_callback_query(callback_query_id, "Некорректная команда")
        except TelegramError:
            logger.exception("Failed to answer invalid callback query")
        return True

    order_id, status_code = parsed
    new_status = ALLOWED_STATUS_TRANSITIONS[status_code]

    try:
        order = Order.objects.prefetch_related("items").get(id=order_id)
    except Order.DoesNotExist:
        try:
            if callback_query_id:
                answer_callback_query(callback_query_id, "Заказ не найден")
        except TelegramError:
            logger.exception("Failed to answer callback for missing order")
        return True

    if not order.can_transition_to(new_status):
        try:
            if callback_query_id:
                label = dict(Order.Status.choices).get(new_status, new_status)
                answer_callback_query(
                    callback_query_id,
                    f"Переход в статус «{label}» недоступен",
                )
        except TelegramError:
            logger.exception("Failed to answer invalid transition callback")
        return True

    order.status = new_status
    order.save(update_fields=["status", "updated_at"])

    try:
        if callback_query_id:
            answer_callback_query(callback_query_id, f"Статус: {order.get_status_display()}")
    except TelegramError:
        logger.exception("Failed to answer callback query")

    fallback_chat = (message.get("chat") or {}).get("id")
    fallback_message_id = message.get("message_id")

    fields_to_update = []

    if not order.telegram_chat_id and fallback_chat is not None:
        order.telegram_chat_id = str(fallback_chat)
        fields_to_update.append("telegram_chat_id")

    if not order.telegram_message_id and fallback_message_id is not None:
        order.telegram_message_id = int(fallback_message_id)
        fields_to_update.append("telegram_message_id")

    if fields_to_update:
        fields_to_update.append("updated_at")
        order.save(update_fields=fields_to_update)

    sync_order_telegram_message(order)
    return True
