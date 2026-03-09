from __future__ import annotations

import json
import os
import urllib.parse
import urllib.request


class TelegramError(RuntimeError):
    pass


def _enabled() -> bool:
    return os.getenv("TELEGRAM_NOTIFICATIONS_ENABLED", "0") == "1"


def _token() -> str:
    token = (os.getenv("TELEGRAM_BOT_TOKEN") or "").strip()
    if not token:
        raise TelegramError("TELEGRAM_BOT_TOKEN is not set")
    return token


def _chat_id() -> str:
    chat_id = (os.getenv("TELEGRAM_CHAT_ID") or "").strip()
    if not chat_id:
        raise TelegramError("TELEGRAM_CHAT_ID is not set")
    return chat_id


def _api_url(method: str) -> str:
    return f"https://api.telegram.org/bot{_token()}/{method}"


def _post(method: str, payload: dict) -> dict:
    url = _api_url(method)

    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        method="POST",
        headers={"Content-Type": "application/json"},
    )

    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            body = resp.read().decode("utf-8")
            result = json.loads(body)
    except Exception as e:
        raise TelegramError(f"Telegram request failed: {e}") from e

    if not result.get("ok"):
        raise TelegramError(f"Telegram API error: {result}")

    return result


def send_message(text: str, reply_markup: dict | None = None) -> dict:
    if not _enabled():
        return {}

    payload = {
        "chat_id": _chat_id(),
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }

    if reply_markup:
        payload["reply_markup"] = reply_markup

    return _post("sendMessage", payload)


def edit_message_text(chat_id: str | int, message_id: int, text: str, reply_markup: dict | None = None) -> dict:
    if not _enabled():
        return {}

    payload = {
        "chat_id": chat_id,
        "message_id": message_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }

    if reply_markup:
        payload["reply_markup"] = reply_markup

    return _post("editMessageText", payload)


def answer_callback_query(callback_query_id: str, text: str = "") -> dict:
    if not _enabled():
        return {}

    payload = {
        "callback_query_id": callback_query_id,
    }
    if text:
        payload["text"] = text

    return _post("answerCallbackQuery", payload)