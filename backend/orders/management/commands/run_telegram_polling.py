from __future__ import annotations

import logging
import os
import time

from django.core.management.base import BaseCommand

from integrations.telegram.client import TelegramError, delete_webhook, get_updates
from orders.telegram_handlers import process_telegram_update

logger = logging.getLogger(__name__)


def _polling_enabled() -> bool:
    return os.getenv("TELEGRAM_POLLING_ENABLED", "0").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


class Command(BaseCommand):
    help = "Runs Telegram long polling for inline order status buttons."

    def handle(self, *args, **options):
        self.stdout.write("Telegram polling worker started.")

        offset: int | None = None
        webhook_cleared = False
        disabled_notified = False

        while True:
            if not _polling_enabled():
                if not disabled_notified:
                    logger.info("Telegram polling is disabled. Waiting for TELEGRAM_POLLING_ENABLED=1.")
                    disabled_notified = True
                time.sleep(30)
                continue

            disabled_notified = False

            try:
                if not webhook_cleared:
                    delete_webhook(drop_pending_updates=False)
                    webhook_cleared = True
                    logger.info("Telegram webhook disabled, polling mode is active.")

                updates = get_updates(
                    offset=offset,
                    timeout=30,
                    allowed_updates=["callback_query"],
                )

                for update in updates:
                    update_id = update.get("update_id")
                    try:
                        process_telegram_update(update)
                    except Exception:
                        logger.exception("Failed to process Telegram update %s", update_id)
                    finally:
                        if isinstance(update_id, int):
                            offset = update_id + 1

            except TelegramError as exc:
                webhook_cleared = False
                logger.exception("Telegram polling error: %s", exc)
                time.sleep(5)
            except Exception:
                logger.exception("Unexpected Telegram polling error")
                time.sleep(5)
