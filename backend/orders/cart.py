from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Dict, Iterable, List, Tuple

from catalog.models import Product


CART_SESSION_KEY = "cart_v1"


@dataclass(frozen=True)
class CartLine:
    product: Product
    qty: int
    line_total: Decimal


def _get_cart_dict(session) -> Dict[str, int]:
    cart = session.get(CART_SESSION_KEY)
    if not isinstance(cart, dict):
        cart = {}
        session[CART_SESSION_KEY] = cart
    return cart


def cart_add(session, product_id: int, qty_delta: int = 1) -> None:
    cart = _get_cart_dict(session)
    key = str(int(product_id))
    cart[key] = max(0, int(cart.get(key, 0)) + int(qty_delta))
    if cart[key] <= 0:
        cart.pop(key, None)
    session.modified = True


def cart_set(session, product_id: int, qty: int) -> None:
    cart = _get_cart_dict(session)
    key = str(int(product_id))
    qty = int(qty)
    if qty <= 0:
        cart.pop(key, None)
    else:
        cart[key] = qty
    session.modified = True


def cart_clear(session) -> None:
    session.pop(CART_SESSION_KEY, None)
    session.modified = True


def cart_count(session) -> int:
    cart = _get_cart_dict(session)
    return sum(int(v) for v in cart.values())


def cart_lines(session) -> Tuple[List[CartLine], Decimal]:
    cart = _get_cart_dict(session)
    if not cart:
        return [], Decimal("0.00")

    ids = [int(pid) for pid in cart.keys()]
    # products = {p.id: p for p in Product.objects.filter(id__in=ids, is_active=True).select_related("category")}
    products = {
        p.id: p
        for p in Product.objects.filter(id__in=ids, is_active=True)
        .select_related("category")
        .prefetch_related("images")
    }

    lines: List[CartLine] = []
    total = Decimal("0.00")
    for pid_str, qty in cart.items():
        pid = int(pid_str)
        product = products.get(pid)
        if not product:
            continue
        qty = int(qty)
        line_total = (product.price * qty).quantize(Decimal("0.01"))
        lines.append(CartLine(product=product, qty=qty, line_total=line_total))
        total += line_total

    total = total.quantize(Decimal("0.01"))
    lines.sort(key=lambda x: (x.product.category_id, x.product.sort_order, x.product.name))
    return lines, total


def cart_get_qty(session, product_id: int) -> int:
    cart = _get_cart_dict(session)
    return int(cart.get(str(int(product_id)), 0))