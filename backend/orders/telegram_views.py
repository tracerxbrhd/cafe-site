from __future__ import annotations

import json
import logging
import os

from django.http import HttpResponse, HttpResponseForbidden, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from .telegram_handlers import process_telegram_update

logger = logging.getLogger(__name__)


def _webhook_secret() -> str:
    return (os.getenv("TELEGRAM_WEBHOOK_SECRET") or "").strip()


@csrf_exempt
@require_POST
def telegram_webhook(request, secret: str):
    if not _webhook_secret() or secret != _webhook_secret():
        return HttpResponseForbidden("invalid secret")

    try:
        payload = json.loads(request.body.decode("utf-8"))
    except Exception:
        return JsonResponse({"ok": False, "error": "invalid json"}, status=400)

    process_telegram_update(payload)
    return JsonResponse({"ok": True})
