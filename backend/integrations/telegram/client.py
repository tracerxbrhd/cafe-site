from __future__ import annotations

import json
import os
import urllib.request
import urllib.parse


class TelegramError(RuntimeError):
    pass


def _enabled() -> bool:
    return os.getenv("TELEGRAM_NOTIFICATIONS_ENABLED", "0") == "1"


def send_message(text: str) -> None:
    """
    Отправка сообщения в Telegram через Bot API.
    Никаких ретраев/очередей в MVP. Ошибки логируем на уровне вызывающего кода.
    """
    if not _enabled():
        return

    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")

    if not token or not chat_id:
        raise TelegramError("Telegram env vars are not set (TELEGRAM_BOT_TOKEN/TELEGRAM_CHAT_ID)")

    url = f"https://api.telegram.org/bot{token}/sendMessage"

    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }

    data = urllib.parse.urlencode(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST")

    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            body = resp.read().decode("utf-8")
            j = json.loads(body)
            if not j.get("ok"):
                raise TelegramError(f"Telegram API error: {body}")
    except Exception as e:
        raise TelegramError(f"Telegram send failed: {e}") from e