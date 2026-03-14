from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP

from django.utils import timezone

from .models import PromoCode


class PromoCodeError(ValueError):
    pass


@dataclass
class PromoCodeApplication:
    promo: PromoCode
    code: str
    discount_amount: Decimal
    discount_label: str


def normalize_promo_code(raw: str) -> str:
    return (raw or "").strip().upper()


def apply_promo_code(raw_code: str, items_total: Decimal) -> PromoCodeApplication:
    code = normalize_promo_code(raw_code)
    if not code:
        raise PromoCodeError("Введите промокод.")

    promo = PromoCode.objects.filter(code=code, is_active=True).first()
    if not promo:
        raise PromoCodeError("Промокод не найден или неактивен.")

    today = timezone.localdate()
    if promo.valid_until and promo.valid_until < today:
        raise PromoCodeError("Срок действия промокода истёк.")

    if promo.discount_type == PromoCode.DiscountType.PERCENT:
        discount_amount = (
            items_total * Decimal(promo.discount_value) / Decimal("100")
        ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    else:
        discount_amount = Decimal(str(promo.discount_value)).quantize(Decimal("0.01"))

    discount_amount = min(discount_amount, items_total).quantize(Decimal("0.01"))
    if discount_amount <= Decimal("0.00"):
        raise PromoCodeError("Промокод не даёт скидку для текущего заказа.")

    return PromoCodeApplication(
        promo=promo,
        code=promo.code,
        discount_amount=discount_amount,
        discount_label=promo.discount_label,
    )
