from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_POST

from decimal import Decimal
from django.shortcuts import get_object_or_404, redirect
from django.views.decorators.http import require_http_methods
from catalog.models import Product
from .forms import CheckoutForm
from .models import Order, OrderItem

from integrations.telegram.client import send_message, TelegramError
from .notifications import format_new_order_message
import logging

from .cart import _get_cart_dict, cart_get_qty  # добавь импорт (или сделай отдельную функцию cart_get_qty)

from .cart import cart_add, cart_clear, cart_count, cart_lines, cart_set


def cart_page(request):
    lines, total = cart_lines(request.session)
    return render(request, "orders/cart.html", {"lines": lines, "total": total})


def cart_api_summary(request):
    lines, total = cart_lines(request.session)
    return JsonResponse(
        {
            "count": cart_count(request.session),
            "total": str(total),
            "items": [
                {
                    "product_id": line.product.id,
                    "qty": line.qty,
                    "line_total": str(line.line_total),
                }
                for line in lines
            ],
        }
    )


@require_POST
def cart_api_add(request):
    product_id = int(request.POST.get("product_id", "0"))
    qty_delta = int(request.POST.get("qty_delta", "1"))
    cart_add(request.session, product_id=product_id, qty_delta=qty_delta)
    return JsonResponse({"ok": True, "count": cart_count(request.session), "product_id": product_id, "qty": cart_get_qty(request.session, product_id)})


@require_POST
def cart_api_set(request):
    product_id = int(request.POST.get("product_id", "0"))
    qty = int(request.POST.get("qty", "0"))
    cart_set(request.session, product_id=product_id, qty=qty)
    # return JsonResponse({"ok": True, "count": cart_count(request.session)})
    return JsonResponse({"ok": True, "count": cart_count(...), "product_id": product_id, "qty": cart_get_qty(..., product_id)})


@require_POST
def cart_api_clear(request):
    cart_clear(request.session)
    return JsonResponse({"ok": True, "count": 0})


@require_http_methods(["GET", "POST"])
def checkout_page(request):
    lines, total = cart_lines(request.session)
    if not lines:
        return redirect("orders:cart")

    if request.method == "POST":
        form = CheckoutForm(request.POST)
        if form.is_valid():
            order = Order.objects.create(
                status=Order.Status.NEW,
                fulfillment=form.cleaned_data["fulfillment"],
                customer_name=form.cleaned_data["customer_name"],
                customer_phone=form.cleaned_data["customer_phone"],
                customer_comment=form.cleaned_data.get("customer_comment", "") or "",
                address_line=form.cleaned_data.get("address_line", "") or "",
                address_entrance=form.cleaned_data.get("address_entrance", "") or "",
                address_floor=form.cleaned_data.get("address_floor", "") or "",
                address_apartment=form.cleaned_data.get("address_apartment", "") or "",
                total=Decimal("0.00"),
            )

            # Создаём позиции из корзины
            order_total = Decimal("0.00")
            for line in lines:
                item = OrderItem.objects.create(
                    order=order,
                    product=line.product,
                    product_name=line.product.name,
                    unit_price=line.product.price,
                    quantity=line.qty,
                    line_total=line.line_total,
                )
                order_total += item.line_total

            order.total = order_total.quantize(Decimal("0.01"))
            order.save(update_fields=["total"])


            logger = logging.getLogger(__name__)


            try:
                # важно: order.items уже созданы, поэтому message будет с позициями
                send_message(format_new_order_message(order))
            except TelegramError as e:
                # В MVP не ломаем заказ из-за Telegram
                logger.exception("Telegram notification failed: %s", e)

            cart_clear(request.session)
            # return redirect("orders:order_status", public_id=order.public_id)
            return redirect("orders:order_success", public_id=order.public_id)
    else:
        form = CheckoutForm()

    return render(request, "orders/checkout.html", {"form": form, "lines": lines, "total": total})


def order_status_page(request, public_id):
    order = get_object_or_404(Order, public_id=public_id)
    return render(request, "orders/order_status.html", {"order": order})

def order_api_status(request, public_id):
    order = get_object_or_404(Order, public_id=public_id)
    return JsonResponse(
        {
            "status": order.status,
            "status_label": order.get_status_display(),
            "updated_at": order.updated_at.isoformat(),
            "total": str(order.total),
        }
    )


def order_success_page(request, public_id):
    order = get_object_or_404(Order, public_id=public_id)
    return render(request, "orders/order_success.html", {"order": order})