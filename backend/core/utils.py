import json
from dataclasses import dataclass
from decimal import Decimal
from typing import Iterable
from django.utils import timezone

from .models import CafeSettings, DeliveryZone, ServicePage, BusinessLunchWeek, BusinessLunchDay


def get_cafe_settings():
    return CafeSettings.objects.order_by("id").first()


def get_delivery_fee(fulfillment: str) -> Decimal:
    settings = get_cafe_settings()
    if not settings:
        return Decimal("0.00")

    if fulfillment == "delivery":
        return settings.delivery_fee

    return Decimal("0.00")


@dataclass
class DeliveryQuote:
    is_deliverable: bool
    zone: DeliveryZone | None
    delivery_fee: Decimal
    min_order_amount: Decimal
    reason: str = ""


def _point_in_polygon(lon: float, lat: float, polygon: list[list[float]]) -> bool:
    """
    Ray casting algorithm.
    polygon: [[lon, lat], [lon, lat], ...]
    """
    inside = False
    n = len(polygon)
    if n < 3:
        return False

    j = n - 1
    for i in range(n):
        xi, yi = polygon[i]
        xj, yj = polygon[j]

        intersects = ((yi > lat) != (yj > lat)) and (
            lon < (xj - xi) * (lat - yi) / ((yj - yi) or 1e-12) + xi
        )
        if intersects:
            inside = not inside
        j = i

    return inside


def _parse_polygon_json(raw: str) -> list[list[float]]:
    data = json.loads(raw)
    if not isinstance(data, list):
        raise ValueError("polygon_json must be a list")

    polygon: list[list[float]] = []
    for point in data:
        if not isinstance(point, list) or len(point) != 2:
            raise ValueError("each point must be [lon, lat]")
        lon = float(point[0])
        lat = float(point[1])
        polygon.append([lon, lat])

    if len(polygon) < 3:
        raise ValueError("polygon must have at least 3 points")

    return polygon


def find_delivery_zone(lat: float, lon: float) -> DeliveryZone | None:
    zones = DeliveryZone.objects.filter(is_active=True).order_by("sort_order", "name")
    for zone in zones:
        try:
            polygon = _parse_polygon_json(zone.polygon_json)
        except Exception:
            continue

        if _point_in_polygon(lon=lon, lat=lat, polygon=polygon):
            return zone

    return None


def get_delivery_quote(lat: float, lon: float, fulfillment: str) -> DeliveryQuote:
    settings = get_cafe_settings()

    if fulfillment != "delivery":
        return DeliveryQuote(
            is_deliverable=True,
            zone=None,
            delivery_fee=Decimal("0.00"),
            min_order_amount=Decimal("0.00"),
        )

    zone = find_delivery_zone(lat=lat, lon=lon)
    if zone:
        return DeliveryQuote(
            is_deliverable=True,
            zone=zone,
            delivery_fee=zone.delivery_fee,
            min_order_amount=zone.min_order_amount,
        )

    default_fee = settings.delivery_fee if settings else Decimal("0.00")
    default_min = settings.min_order_amount if settings else Decimal("0.00")

    return DeliveryQuote(
        is_deliverable=False,
        zone=None,
        delivery_fee=default_fee,
        min_order_amount=default_min,
        reason="Адрес вне зоны доставки",
    )


# def get_current_business_lunch_menu():
#     today = timezone.localdate()

#     return (
#         BusinessLunchMenu.objects.filter(
#             is_active=True,
#             is_published=True,
#             week_start__lte=today,
#             week_end__gte=today,
#         )
#         .prefetch_related("items")
#         .order_by("-week_start", "sort_order", "-id")
#         .first()
#     )


def get_current_business_lunch_week():
    today = timezone.localdate()

    return (
        BusinessLunchWeek.objects.filter(
            is_active=True,
            is_published=True,
            week_start__lte=today,
            week_end__gte=today,
        )
        .prefetch_related("days__items__product")
        .order_by("-week_start", "sort_order", "-id")
        .first()
    )


def get_current_business_lunch_day():
    today = timezone.localdate()

    return (
        BusinessLunchDay.objects.filter(
            week__is_active=True,
            week__is_published=True,
            week__week_start__lte=today,
            week__week_end__gte=today,
            service_date=today,
            is_active=True,
        )
        .prefetch_related("items__product")
        .select_related("week")
        .order_by("sort_order", "id")
        .first()
    )


def get_service_page(page_type: str):
    return (
        ServicePage.objects.filter(page_type=page_type, is_published=True)
        .order_by("id")
        .first()
    )