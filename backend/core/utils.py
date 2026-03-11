from decimal import Decimal
from .models import CafeSettings


def get_cafe_settings():
    return CafeSettings.objects.order_by("id").first()


def get_delivery_fee(fulfillment: str) -> Decimal:
    settings = get_cafe_settings()
    if not settings:
        return Decimal("0.00")

    if fulfillment == "delivery":
        return settings.delivery_fee

    return Decimal("0.00")