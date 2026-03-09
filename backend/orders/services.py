from __future__ import annotations

import logging

from integrations.telegram.client import TelegramError, edit_message_text
from .models import Order
from .notifications import build_order_status_keyboard, format_new_order_message

logger = logging.getLogger(__name__)


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