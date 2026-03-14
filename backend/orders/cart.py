from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from catalog.models import Product
from core.models import BusinessLunchDay


CART_SESSION_KEY = "cart"
LUNCH_CART_SESSION_KEY = "business_lunch_cart"


@dataclass
class CartLine:
    kind: str  # "product" | "business_lunch"
    product: Product | None
    lunch_day: BusinessLunchDay | None
    qty: int
    unit_price: Decimal
    line_total: Decimal


def _get_cart_dict(session) -> dict[str, int]:
    return session.get(CART_SESSION_KEY, {})


def _save_cart_dict(session, cart: dict[str, int]) -> None:
    session[CART_SESSION_KEY] = cart
    session.modified = True


def _get_lunch_cart_dict(session) -> dict[str, int]:
    return session.get(LUNCH_CART_SESSION_KEY, {})


def _save_lunch_cart_dict(session, cart: dict[str, int]) -> None:
    session[LUNCH_CART_SESSION_KEY] = cart
    session.modified = True


def cart_get_qty(session, product_id: int) -> int:
    cart = _get_cart_dict(session)
    return int(cart.get(str(product_id), 0))


def lunch_get_qty(session, lunch_day_id: int) -> int:
    cart = _get_lunch_cart_dict(session)
    return int(cart.get(str(lunch_day_id), 0))


def cart_add(session, product_id: int, qty_delta: int = 1) -> int:
    cart = _get_cart_dict(session)
    key = str(product_id)
    current = int(cart.get(key, 0))
    new_qty = max(0, current + qty_delta)

    if new_qty > 0:
        cart[key] = new_qty
    else:
        cart.pop(key, None)

    _save_cart_dict(session, cart)
    return new_qty


def cart_set(session, product_id: int, qty: int) -> int:
    cart = _get_cart_dict(session)
    key = str(product_id)
    qty = max(0, int(qty))

    if qty > 0:
        cart[key] = qty
    else:
        cart.pop(key, None)

    _save_cart_dict(session, cart)
    return qty


def add_business_lunch(session, lunch_day_id: int, qty_delta: int = 1) -> int:
    cart = _get_lunch_cart_dict(session)
    key = str(lunch_day_id)
    current = int(cart.get(key, 0))
    new_qty = max(0, current + qty_delta)

    if new_qty > 0:
        cart[key] = new_qty
    else:
        cart.pop(key, None)

    _save_lunch_cart_dict(session, cart)
    return new_qty


def set_business_lunch_qty(session, lunch_day_id: int, qty: int) -> int:
    cart = _get_lunch_cart_dict(session)
    key = str(lunch_day_id)
    qty = max(0, int(qty))

    if qty > 0:
        cart[key] = qty
    else:
        cart.pop(key, None)

    _save_lunch_cart_dict(session, cart)
    return qty


def cart_count(session) -> int:
    product_count = sum(_get_cart_dict(session).values())
    lunch_count = sum(_get_lunch_cart_dict(session).values())
    return product_count + lunch_count


def cart_clear(session) -> None:
    session.pop(CART_SESSION_KEY, None)
    session.pop(LUNCH_CART_SESSION_KEY, None)
    session.modified = True


def cart_lines(session):
    lines: list[CartLine] = []
    total = Decimal("0.00")

    product_cart = _get_cart_dict(session)
    product_ids = [int(k) for k in product_cart.keys()] if product_cart else []
    products = {
        p.id: p
        for p in Product.objects.filter(id__in=product_ids, is_active=True)
        .select_related("category")
        .prefetch_related("images")
    }

    for pid_str, qty in product_cart.items():
        product = products.get(int(pid_str))
        if not product:
            continue

        qty = int(qty)
        unit_price = product.price
        line_total = unit_price * qty

        lines.append(
            CartLine(
                kind="product",
                product=product,
                lunch_day=None,
                qty=qty,
                unit_price=unit_price,
                line_total=line_total,
            )
        )
        total += line_total

    lunch_cart = _get_lunch_cart_dict(session)
    lunch_ids = [int(k) for k in lunch_cart.keys()] if lunch_cart else []
    lunch_days = {
        d.id: d
        for d in BusinessLunchDay.objects.filter(id__in=lunch_ids, is_active=True)
        .select_related("week")
        .prefetch_related("items__product")
    }

    for lid_str, qty in lunch_cart.items():
        lunch_day = lunch_days.get(int(lid_str))
        if not lunch_day:
            continue

        qty = int(qty)
        unit_price = lunch_day.price
        line_total = unit_price * qty

        lines.append(
            CartLine(
                kind="business_lunch",
                product=None,
                lunch_day=lunch_day,
                qty=qty,
                unit_price=unit_price,
                line_total=line_total,
            )
        )
        total += line_total

    return lines, total.quantize(Decimal("0.01"))