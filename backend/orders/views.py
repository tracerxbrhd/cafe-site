# from django.http import JsonResponse
# from django.views.decorators.http import require_POST, require_http_methods

# import logging
# from decimal import Decimal
# from django.shortcuts import get_object_or_404, redirect, render
# from core.models import BusinessLunchDay
# from catalog.models import Product
# from .forms import CheckoutForm
# from .models import Order, OrderItem

# from integrations.telegram.client import send_message, TelegramError
# from .notifications import format_new_order_message, build_order_status_keyboard

# from core.utils import get_cafe_settings, get_delivery_quote
# from django.contrib import messages

# from .cart import _get_cart_dict, cart_get_qty  # добавь импорт (или сделай отдельную функцию cart_get_qty)

# from .cart import (
#     add_business_lunch,
#     cart_add,
#     cart_clear,
#     cart_count,
#     cart_lines,
#     cart_set,
# )
from decimal import Decimal
import logging

from django.contrib import messages
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST, require_http_methods

from core.models import BusinessLunchDay
from core.utils import get_cafe_settings, get_delivery_quote
from integrations.telegram.client import TelegramError, send_message

from .cart import (
    CART_SESSION_KEY,
    add_business_lunch,
    cart_add,
    cart_clear,
    cart_count,
    cart_get_qty,
    cart_lines,
    cart_set,
    lunch_get_qty,
)
from .forms import CheckoutForm
from .models import Order, OrderItem
from .notifications import build_order_status_keyboard, format_new_order_message




def cart_page(request):
    lines, total = cart_lines(request.session)
    return render(request, "orders/cart.html", {"lines": lines, "total": total})


# def cart_api_summary(request):
#     lines, total = cart_lines(request.session)
#     return JsonResponse(
#         {
#             "count": cart_count(request.session),
#             "total": str(total),
#             "items": [
#                 {
#                     "product_id": line.product.id,
#                     "qty": line.qty,
#                     "line_total": str(line.line_total),
#                 }
#                 for line in lines
#             ],
#         }
#     )
def cart_api_summary(request):
    lines, total = cart_lines(request.session)

    items = []
    for line in lines:
        if line.kind == "product" and line.product:
            items.append(
                {
                    "kind": "product",
                    "product_id": line.product.id,
                    "qty": line.qty,
                    "line_total": str(line.line_total),
                }
            )
        elif line.kind == "business_lunch" and line.lunch_day:
            items.append(
                {
                    "kind": "business_lunch",
                    "lunch_day_id": line.lunch_day.id,
                    "qty": line.qty,
                    "line_total": str(line.line_total),
                }
            )

    return JsonResponse(
        {
            "count": cart_count(request.session),
            "total": str(total),
            "items": items,
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


# @require_http_methods(["GET", "POST"])
# def checkout_page(request):
#     lines, items_total = cart_lines(request.session)
#     if not lines:
#         return redirect("orders:cart")

#     cafe_settings = get_cafe_settings()

#     if cafe_settings:
#         if not cafe_settings.is_currently_open():
#             messages.error(
#                 request,
#                 f"Сейчас приём заказов недоступен. Режим работы: {cafe_settings.working_hours_text}."
#             )
#             return redirect("orders:cart")

#     if request.method == "POST":
#         form = CheckoutForm(request.POST)
#         if form.is_valid():
#             fulfillment = form.cleaned_data["fulfillment"]

#             delivery_fee = Decimal("0.00")
#             min_order_amount = cafe_settings.min_order_amount if cafe_settings else Decimal("0.00")

#             if fulfillment == Order.Fulfillment.DELIVERY:
#                 lat = float(form.cleaned_data["delivery_lat"])
#                 lon = float(form.cleaned_data["delivery_lon"])
#                 quote = get_delivery_quote(lat=lat, lon=lon, fulfillment=fulfillment)

#                 if not quote.is_deliverable:
#                     form.add_error("address_line", quote.reason or "Адрес вне зоны доставки.")
#                 else:
#                     delivery_fee = quote.delivery_fee
#                     min_order_amount = quote.min_order_amount
#             else:
#                 quote = None

#             grand_total = items_total + delivery_fee

#             if not form.errors:
#                 if grand_total < min_order_amount:
#                     form.add_error(
#                         None,
#                         f"Минимальная сумма заказа: {min_order_amount} ₽."
#                     )
#                 else:
#                     order = Order.objects.create(
#                         status=Order.Status.NEW,
#                         fulfillment=fulfillment,
#                         customer_name=form.cleaned_data["customer_name"],
#                         customer_phone=form.cleaned_data["customer_phone"],
#                         customer_comment=form.cleaned_data.get("customer_comment", "") or "",
#                         address_line=form.cleaned_data.get("address_line", "") or "",
#                         address_entrance=form.cleaned_data.get("address_entrance", "") or "",
#                         address_floor=form.cleaned_data.get("address_floor", "") or "",
#                         address_apartment=form.cleaned_data.get("address_apartment", "") or "",
#                         total=Decimal("0.00"),
#                     )

#                     order_total = Decimal("0.00")
#                     for line in lines:
#                         item = OrderItem.objects.create(
#                             order=order,
#                             product=line.product,
#                             product_name=line.product.name,
#                             unit_price=line.product.price,
#                             quantity=line.qty,
#                             line_total=line.line_total,
#                         )
#                         order_total += item.line_total

#                     order_total += delivery_fee
#                     order.total = order_total.quantize(Decimal("0.01"))
#                     order.save(update_fields=["total"])


#             logger = logging.getLogger(__name__)


#             try:
#                 result = send_message(
#                     format_new_order_message(order),
#                     reply_markup=build_order_status_keyboard(order),
#                 )

#                 telegram_result = (result or {}).get("result") or {}
#                 chat = telegram_result.get("chat") or {}
#                 message_id = telegram_result.get("message_id")

#                 chat_id = chat.get("id")
#                 if chat_id is not None and message_id is not None:
#                     order.telegram_chat_id = str(chat_id)
#                     order.telegram_message_id = int(message_id)
#                     order.save(update_fields=["telegram_chat_id", "telegram_message_id", "updated_at"])
#             except TelegramError as e:
#                 # В MVP не ломаем заказ из-за Telegram
#                 logger.exception("Telegram notification failed: %s", e)

#             cart_clear(request.session)
#             # return redirect("orders:order_status", public_id=order.public_id)
#             return redirect("orders:order_success", public_id=order.public_id)
#     else:
#         form = CheckoutForm()


#     selected_fulfillment = (
#         form.data.get("fulfillment")
#         if request.method == "POST"
#         else Order.Fulfillment.DELIVERY
#     )

#     delivery_fee = get_delivery_fee(selected_fulfillment)
#     grand_total = items_total + delivery_fee


#     selected_fulfillment = (
#         form.data.get("fulfillment")
#         if request.method == "POST"
#         else Order.Fulfillment.DELIVERY
#     )

#     delivery_fee = Decimal("0.00")
#     grand_total = items_total

#     if selected_fulfillment == Order.Fulfillment.DELIVERY and request.method == "POST":
#         try:
#             lat = float((form.data.get("delivery_lat") or "").strip())
#             lon = float((form.data.get("delivery_lon") or "").strip())
#             quote = get_delivery_quote(lat=lat, lon=lon, fulfillment=selected_fulfillment)
#             if quote.is_deliverable:
#                 delivery_fee = quote.delivery_fee
#                 grand_total = items_total + delivery_fee
#         except Exception:
#             pass

#     # return render(request, "orders/checkout.html", {"form": form, "lines": lines, "total": total})
#     return render(
#         request,
#         "orders/checkout.html",
#         {
#             "form": form,
#             "lines": lines,
#             "items_total": items_total,
#             "delivery_fee": delivery_fee,
#             "grand_total": grand_total,
#         },
#     )
# @require_http_methods(["GET", "POST"])
# def checkout_page(request):
#     lines, items_total = cart_lines(request.session)
#     if not lines:
#         return redirect("orders:cart")

#     cafe_settings = get_cafe_settings()

#     if cafe_settings:
#         if not cafe_settings.is_currently_open():
#             messages.error(
#                 request,
#                 f"Сейчас приём заказов недоступен. Режим работы: {cafe_settings.working_hours_text}."
#             )
#             return redirect("orders:cart")

#     form = CheckoutForm(request.POST or None)

#     if request.method == "POST":
#         if form.is_valid():
#             fulfillment = form.cleaned_data["fulfillment"]

#             delivery_fee = Decimal("0.00")
#             min_order_amount = cafe_settings.min_order_amount if cafe_settings else Decimal("0.00")

#             if fulfillment == Order.Fulfillment.DELIVERY:
#                 lat = float(form.cleaned_data["delivery_lat"])
#                 lon = float(form.cleaned_data["delivery_lon"])
#                 quote = get_delivery_quote(lat=lat, lon=lon, fulfillment=fulfillment)

#                 if not quote.is_deliverable:
#                     form.add_error("address_line", quote.reason or "Адрес вне зоны доставки.")
#                 else:
#                     delivery_fee = quote.delivery_fee
#                     min_order_amount = quote.min_order_amount
#             else:
#                 quote = None

#             grand_total = items_total + delivery_fee

#             if not form.errors:
#                 if grand_total < min_order_amount:
#                     form.add_error(
#                         None,
#                         f"Минимальная сумма заказа: {min_order_amount} ₽."
#                     )
#                 else:
#                     order = Order.objects.create(
#                         status=Order.Status.NEW,
#                         fulfillment=fulfillment,
#                         customer_name=form.cleaned_data["customer_name"],
#                         customer_phone=form.cleaned_data["customer_phone"],
#                         customer_comment=form.cleaned_data.get("customer_comment", "") or "",
#                         address_line=form.cleaned_data.get("address_line", "") or "",
#                         address_entrance=form.cleaned_data.get("address_entrance", "") or "",
#                         address_floor=form.cleaned_data.get("address_floor", "") or "",
#                         address_apartment=form.cleaned_data.get("address_apartment", "") or "",
#                         total=Decimal("0.00"),
#                     )

#                     order_total = Decimal("0.00")
#                     for line in lines:
#                         item = OrderItem.objects.create(
#                             order=order,
#                             product=line.product,
#                             product_name=line.product.name,
#                             unit_price=line.product.price,
#                             quantity=line.qty,
#                             line_total=line.line_total,
#                         )
#                         order_total += item.line_total

#                     order_total += delivery_fee
#                     order.total = order_total.quantize(Decimal("0.01"))
#                     order.save(update_fields=["total"])

#                     logger = logging.getLogger(__name__)

#                     try:
#                         result = send_message(
#                             format_new_order_message(order),
#                             reply_markup=build_order_status_keyboard(order),
#                         )

#                         telegram_result = (result or {}).get("result") or {}
#                         chat = telegram_result.get("chat") or {}
#                         message_id = telegram_result.get("message_id")

#                         chat_id = chat.get("id")
#                         if chat_id is not None and message_id is not None:
#                             order.telegram_chat_id = str(chat_id)
#                             order.telegram_message_id = int(message_id)
#                             order.save(update_fields=["telegram_chat_id", "telegram_message_id", "updated_at"])

#                     except TelegramError as e:
#                         logger.exception("Telegram notification failed: %s", e)

#                     cart_clear(request.session)
#                     return redirect("orders:order_success", public_id=order.public_id)

#     selected_fulfillment = (
#         form.data.get("fulfillment")
#         if request.method == "POST"
#         else Order.Fulfillment.DELIVERY
#     )

#     delivery_fee = Decimal("0.00")
#     grand_total = items_total

#     if selected_fulfillment == Order.Fulfillment.DELIVERY and request.method == "POST":
#         try:
#             lat = float((form.data.get("delivery_lat") or "").strip())
#             lon = float((form.data.get("delivery_lon") or "").strip())
#             quote = get_delivery_quote(lat=lat, lon=lon, fulfillment=selected_fulfillment)
#             if quote.is_deliverable:
#                 delivery_fee = quote.delivery_fee
#                 grand_total = items_total + delivery_fee
#         except Exception:
#             pass

#     return render(
#         request,
#         "orders/checkout.html",
#         {
#             "form": form,
#             "lines": lines,
#             "items_total": items_total,
#             "delivery_fee": delivery_fee,
#             "grand_total": grand_total,
#         },
#     )
@require_http_methods(["GET", "POST"])
def checkout_page(request):
    lines, items_total = cart_lines(request.session)
    if not lines:
        return redirect("orders:cart")

    cafe_settings = get_cafe_settings()

    if cafe_settings and not cafe_settings.is_currently_open():
        messages.error(
            request,
            f"Сейчас приём заказов недоступен. Режим работы: {cafe_settings.working_hours_text}."
        )
        return redirect("orders:cart")

    form = CheckoutForm(request.POST or None)

    delivery_fee = Decimal("0.00")
    grand_total = items_total

    if request.method == "POST" and form.is_valid():
        fulfillment = form.cleaned_data["fulfillment"]
        min_order_amount = cafe_settings.min_order_amount if cafe_settings else Decimal("0.00")

        quote = None
        delivery_lat = None
        delivery_lon = None

        if fulfillment == Order.Fulfillment.DELIVERY:
            delivery_lat = float(form.cleaned_data["delivery_lat"])
            delivery_lon = float(form.cleaned_data["delivery_lon"])
            quote = get_delivery_quote(
                lat=delivery_lat,
                lon=delivery_lon,
                fulfillment=fulfillment,
            )

            if not quote.is_deliverable:
                form.add_error(
                    "address_line",
                    quote.reason or "Адрес вне зоны доставки."
                )
            else:
                delivery_fee = quote.delivery_fee
                min_order_amount = quote.min_order_amount
        else:
            delivery_fee = Decimal("0.00")

        grand_total = items_total + delivery_fee

        # Рекомендуемая логика: минимальная сумма считается по товарам, без доставки
        if not form.errors and items_total < min_order_amount:
            form.add_error(
                None,
                f"Минимальная сумма заказа: {min_order_amount} ₽."
            )

        if not form.errors:
            order = Order.objects.create(
                status=Order.Status.NEW,
                fulfillment=fulfillment,
                customer_name=form.cleaned_data["customer_name"],
                customer_phone=form.cleaned_data["customer_phone"],
                customer_comment=form.cleaned_data.get("customer_comment", "") or "",
                address_line=form.cleaned_data.get("address_line", "") or "",
                address_entrance=form.cleaned_data.get("address_entrance", "") or "",
                address_floor=form.cleaned_data.get("address_floor", "") or "",
                address_apartment=form.cleaned_data.get("address_apartment", "") or "",
                delivery_lat=Decimal(str(delivery_lat)).quantize(Decimal("0.000001")) if delivery_lat is not None else None,
                delivery_lon=Decimal(str(delivery_lon)).quantize(Decimal("0.000001")) if delivery_lon is not None else None,
                delivery_zone_code=quote.zone.code if quote and quote.zone else "",
                delivery_zone_name=quote.zone.name if quote and quote.zone else "",
                delivery_fee=delivery_fee,
                total=Decimal("0.00"),
            )

            order_total = Decimal("0.00")

            # for line in lines:
            #     item = OrderItem.objects.create(
            #         order=order,
            #         product=line.product,
            #         product_name=line.product.name,
            #         unit_price=line.product.price,
            #         quantity=line.qty,
            #         line_total=line.line_total,
            #     )
            #     order_total += item.line_total
            for line in lines:
                if line.kind == "product" and line.product:
                    item = OrderItem.objects.create(
                        order=order,
                        product=line.product,
                        product_name=line.product.name,
                        unit_price=line.unit_price,
                        quantity=line.qty,
                        line_total=line.line_total,
                    )
                elif line.kind == "business_lunch" and line.lunch_day:
                    composition_parts = []
                    for comp in line.lunch_day.items.all():
                        if comp.role:
                            composition_parts.append(f"{comp.role}: {comp.product.name}")
                        else:
                            composition_parts.append(comp.product.name)

                    item = OrderItem.objects.create(
                        order=order,
                        product=None,
                        product_name=line.lunch_day.display_name,
                        unit_price=line.unit_price,
                        quantity=line.qty,
                        line_total=line.line_total,
                    )
                else:
                    continue

                order_total += item.line_total

            order_total += delivery_fee
            order.total = order_total.quantize(Decimal("0.01"))
            order.save(update_fields=["total"])

            logger = logging.getLogger(__name__)

            try:
                result = send_message(
                    format_new_order_message(order),
                    reply_markup=build_order_status_keyboard(order),
                )

                telegram_result = (result or {}).get("result") or {}
                chat = telegram_result.get("chat") or {}
                message_id = telegram_result.get("message_id")
                chat_id = chat.get("id")

                if chat_id is not None and message_id is not None:
                    order.telegram_chat_id = str(chat_id)
                    order.telegram_message_id = int(message_id)
                    order.save(
                        update_fields=[
                            "telegram_chat_id",
                            "telegram_message_id",
                            "updated_at",
                        ]
                    )

            except TelegramError as e:
                logger.exception("Telegram notification failed: %s", e)

            cart_clear(request.session)
            return redirect("orders:order_success", public_id=order.public_id)

    # Предварительный расчёт для отображения формы
    selected_fulfillment = (
        form.data.get("fulfillment")
        if request.method == "POST"
        else Order.Fulfillment.DELIVERY
    )

    if selected_fulfillment == Order.Fulfillment.DELIVERY and request.method == "POST":
        try:
            lat = float((form.data.get("delivery_lat") or "").strip())
            lon = float((form.data.get("delivery_lon") or "").strip())
            quote = get_delivery_quote(
                lat=lat,
                lon=lon,
                fulfillment=selected_fulfillment,
            )
            if quote.is_deliverable:
                delivery_fee = quote.delivery_fee
        except Exception:
            delivery_fee = Decimal("0.00")

    grand_total = items_total + delivery_fee

    return render(
        request,
        "orders/checkout.html",
        {
            "form": form,
            "lines": lines,
            "items_total": items_total,
            "delivery_fee": delivery_fee,
            "grand_total": grand_total,
        },
    )


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


@require_POST
def delivery_api_quote(request):
    try:
        lat = float(request.POST.get("lat", "").strip())
        lon = float(request.POST.get("lon", "").strip())
    except Exception:
        return JsonResponse({"ok": False, "error": "Некорректные координаты"}, status=400)

    fulfillment = (request.POST.get("fulfillment") or "delivery").strip()
    quote = get_delivery_quote(lat=lat, lon=lon, fulfillment=fulfillment)

    return JsonResponse(
        {
            "ok": True,
            "is_deliverable": quote.is_deliverable,
            "zone_code": quote.zone.code if quote.zone else "",
            "zone_name": quote.zone.name if quote.zone else "",
            "delivery_fee": str(quote.delivery_fee),
            "min_order_amount": str(quote.min_order_amount),
            "reason": quote.reason,
        }
    )



@require_POST
def cart_api_add_business_lunch(request):
    try:
        lunch_day_id = int(request.POST.get("lunch_day_id", "0"))
        qty_delta = int(request.POST.get("qty_delta", "1"))
    except ValueError:
        return JsonResponse({"ok": False, "error": "Некорректные параметры"}, status=400)

    lunch_day = BusinessLunchDay.objects.filter(id=lunch_day_id, is_active=True).first()
    if not lunch_day:
        return JsonResponse({"ok": False, "error": "Бизнес-ланч не найден"}, status=404)

    qty = add_business_lunch(request.session, lunch_day_id=lunch_day_id, qty_delta=qty_delta)

    return JsonResponse(
        {
            "ok": True,
            "kind": "business_lunch",
            "lunch_day_id": lunch_day.id,
            "qty": qty,
            "count": cart_count(request.session),
        }
    )