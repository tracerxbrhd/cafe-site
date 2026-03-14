from __future__ import annotations

import base64
import json
from dataclasses import dataclass
from decimal import Decimal
from urllib import error, request

from django.conf import settings


class YooKassaError(Exception):
    pass


class YooKassaConfigurationError(YooKassaError):
    pass


@dataclass
class YooKassaPayment:
    payment_id: str
    status: str
    confirmation_url: str
    raw: dict


def is_yookassa_configured() -> bool:
    return bool(settings.YOOKASSA_SHOP_ID and settings.YOOKASSA_SECRET_KEY)


def create_payment(
    *,
    amount: Decimal,
    description: str,
    return_url: str,
    idempotence_key: str,
    metadata: dict | None = None,
) -> YooKassaPayment:
    payload = {
        "amount": {
            "value": str(Decimal(str(amount)).quantize(Decimal("0.01"))),
            "currency": "RUB",
        },
        "capture": True,
        "confirmation": {
            "type": "redirect",
            "return_url": return_url,
        },
        "description": description,
        "metadata": metadata or {},
    }
    data = _request_json(
        method="POST",
        path="/payments",
        payload=payload,
        extra_headers={"Idempotence-Key": str(idempotence_key)},
    )
    return _payment_from_payload(data)


def get_payment(payment_id: str) -> YooKassaPayment:
    data = _request_json(method="GET", path=f"/payments/{payment_id}")
    return _payment_from_payload(data)


def _payment_from_payload(data: dict) -> YooKassaPayment:
    confirmation = data.get("confirmation") or {}
    return YooKassaPayment(
        payment_id=str(data.get("id") or ""),
        status=str(data.get("status") or ""),
        confirmation_url=str(confirmation.get("confirmation_url") or ""),
        raw=data,
    )


def _request_json(
    *,
    method: str,
    path: str,
    payload: dict | None = None,
    extra_headers: dict | None = None,
) -> dict:
    if not is_yookassa_configured():
        raise YooKassaConfigurationError(
            "ЮKassa не настроена. Добавьте YOOKASSA_SHOP_ID и YOOKASSA_SECRET_KEY."
        )

    body = None
    headers = {
        "Authorization": _build_auth_header(),
        "Accept": "application/json",
    }
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"

    if extra_headers:
        headers.update(extra_headers)

    endpoint = f"{settings.YOOKASSA_API_URL.rstrip('/')}{path}"
    req = request.Request(
        endpoint,
        data=body,
        headers=headers,
        method=method.upper(),
    )

    try:
        with request.urlopen(req, timeout=20) as response:
            return json.loads(response.read().decode("utf-8"))
    except error.HTTPError as exc:
        details = _extract_error_details(exc)
        raise YooKassaError(details) from exc
    except error.URLError as exc:
        raise YooKassaError("Не удалось связаться с ЮKassa. Проверьте интернет и ключи.") from exc


def _build_auth_header() -> str:
    raw = f"{settings.YOOKASSA_SHOP_ID}:{settings.YOOKASSA_SECRET_KEY}".encode("utf-8")
    token = base64.b64encode(raw).decode("ascii")
    return f"Basic {token}"


def _extract_error_details(exc: error.HTTPError) -> str:
    try:
        payload = json.loads(exc.read().decode("utf-8"))
    except Exception:
        return f"ЮKassa вернула HTTP {exc.code}."

    description = payload.get("description") or payload.get("type") or ""
    if description:
        return f"ЮKassa: {description}"
    return f"ЮKassa вернула HTTP {exc.code}."
