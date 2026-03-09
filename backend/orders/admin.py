from urllib.parse import urlencode

from django.contrib import admin, messages
from django.http import HttpResponseRedirect
from django.urls import path, reverse
from django.utils.html import format_html, format_html_join
from django.db.models import Sum
from django.utils import timezone
from django.http import JsonResponse

from django.utils.safestring import mark_safe
from django.views.decorators.http import require_POST

# from django.middleware.csrf import get_token

from .models import Order, OrderItem
from .services import sync_order_telegram_message


class ActiveOrderFilter(admin.SimpleListFilter):
    title = "Состояние заказа"
    parameter_name = "activity"

    def lookups(self, request, model_admin):
        return (
            ("all", "Все"),
            ("active", "Активные"),
            ("closed", "Завершённые"),
        )

    def queryset(self, request, queryset):
        value = self.value()

        if value == "all":
            return queryset

        if value == "closed":
            return queryset.filter(
                status__in=[Order.Status.DONE, Order.Status.CANCELED]
            )

        # по умолчанию: active
        return queryset.exclude(
            status__in=[Order.Status.DONE, Order.Status.CANCELED]
        )

    def choices(self, changelist):
        value = self.value() or "active"

        for lookup, title in self.lookup_choices:
            yield {
                "selected": value == lookup,
                "query_string": changelist.get_query_string(
                    {self.parameter_name: lookup},
                    [],
                ),
                "display": title,
            }

class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ("product", "product_name", "unit_price", "quantity", "line_total")
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False


def _apply_status_transition(modeladmin, request, queryset, target_status: str, label: str):
    updated = 0
    skipped = 0
    telegram_synced = 0

    for order in queryset:
        if not order.can_transition_to(target_status):
            skipped += 1
            continue

        order.status = target_status
        order.save(update_fields=["status", "updated_at"])
        updated += 1

        if sync_order_telegram_message(order):
            telegram_synced += 1

    if updated:
        modeladmin.message_user(
            request,
            f"Статус «{label}» установлен для {updated} заказ(ов). Telegram обновлён для {telegram_synced}.",
            level=messages.SUCCESS,
        )

    if skipped:
        modeladmin.message_user(
            request,
            f"{skipped} заказ(ов) пропущено: недопустимый переход статуса.",
            level=messages.WARNING,
        )


@admin.action(description='Перевести в «Подтверждён»')
def mark_confirmed(modeladmin, request, queryset):
    _apply_status_transition(modeladmin, request, queryset, Order.Status.CONFIRMED, "Подтверждён")


@admin.action(description='Перевести в «Готовится»')
def mark_cooking(modeladmin, request, queryset):
    _apply_status_transition(modeladmin, request, queryset, Order.Status.COOKING, "Готовится")


@admin.action(description='Перевести в «В пути»')
def mark_on_the_way(modeladmin, request, queryset):
    _apply_status_transition(modeladmin, request, queryset, Order.Status.ON_THE_WAY, "В пути")


@admin.action(description='Перевести в «Выполнен»')
def mark_done(modeladmin, request, queryset):
    _apply_status_transition(modeladmin, request, queryset, Order.Status.DONE, "Выполнен")


@admin.action(description='Перевести в «Отменён»')
def mark_canceled(modeladmin, request, queryset):
    _apply_status_transition(modeladmin, request, queryset, Order.Status.CANCELED, "Отменён")


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "status_badge",
        "fulfillment",
        "customer_name",
        "customer_phone",
        "short_items",
        "short_address",
        "total",
        "created_at",
        "public_link",
    )
    list_filter = (
        ActiveOrderFilter,
        "status",
        "fulfillment",
        "created_at",
    )
    search_fields = (
        "id",
        "customer_name",
        "customer_phone",
        "public_id",
        "address_line",
    )
    readonly_fields = (
        "public_id",
        "total",
        "created_at",
        "updated_at",
        "telegram_chat_id",
        "telegram_message_id",
        "status_controls",
    )
    ordering = ("-created_at",)
    date_hierarchy = "created_at"
    inlines = [OrderItemInline]
    actions = [mark_confirmed, mark_cooking, mark_on_the_way, mark_done, mark_canceled]

    fieldsets = (
        (
            "Основное",
            {
                "fields": (
                    "status",
                    "status_controls",
                    "fulfillment",
                    "total",
                    "public_id",
                )
            },
        ),
        (
            "Клиент",
            {
                "fields": (
                    "customer_name",
                    "customer_phone",
                    "customer_comment",
                )
            },
        ),
        (
            "Адрес",
            {
                "fields": (
                    "address_line",
                    "address_entrance",
                    "address_floor",
                    "address_apartment",
                )
            },
        ),
        (
            "Telegram",
            {
                "classes": ("collapse",),
                "fields": (
                    "telegram_chat_id",
                    "telegram_message_id",
                )
            },
        ),
        (
            "Системное",
            {
                "classes": ("collapse",),
                "fields": (
                    "created_at",
                    "updated_at",
                )
            },
        ),
    )

    change_list_template = "admin/orders/order/change_list.html"

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.prefetch_related("items")

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                "live-summary/",
                self.admin_site.admin_view(self.live_summary_view),
                name="orders_order_live_summary",
            ),
            path(
                "<int:order_id>/set-status/<str:target_status>/",
                self.admin_site.admin_view(require_POST(self.set_status_view)),
                name="orders_order_set_status",
            ),
        ]
        return custom_urls + urls

    def set_status_view(self, request, order_id: int, target_status: str):
        order = self.get_queryset(request).filter(pk=order_id).first()
        if not order:
            self.message_user(request, "Заказ не найден.", level=messages.ERROR)
            return HttpResponseRedirect(reverse("admin:orders_order_changelist"))

        if target_status not in dict(Order.Status.choices):
            self.message_user(request, "Некорректный статус.", level=messages.ERROR)
            return HttpResponseRedirect(reverse("admin:orders_order_change", args=[order.id]))

        if not order.can_transition_to(target_status):
            self.message_user(
                request,
                f"Переход из статуса «{order.get_status_display()}» недоступен.",
                level=messages.WARNING,
            )
            return HttpResponseRedirect(reverse("admin:orders_order_change", args=[order.id]))

        order.status = target_status
        order.save(update_fields=["status", "updated_at"])

        telegram_synced = sync_order_telegram_message(order)
        label = dict(Order.Status.choices).get(target_status, target_status)

        msg = f"Статус заказа изменён на «{label}»."
        if telegram_synced:
            msg += " Telegram обновлён."

        self.message_user(request, msg, level=messages.SUCCESS)
        return HttpResponseRedirect(reverse("admin:orders_order_change", args=[order.id]))

    def status_controls(self, obj):
        if not obj:
            return "—"

        allowed = list(obj.allowed_next_statuses())
        if not allowed:
            return "Нет доступных переходов"

        labels = dict(Order.Status.choices)
        ordered_statuses = [
            Order.Status.CONFIRMED,
            Order.Status.COOKING,
            Order.Status.ON_THE_WAY,
            Order.Status.DONE,
            Order.Status.CANCELED,
        ]

        buttons = []

        for status in ordered_statuses:
            if status not in allowed:
                continue

            url = reverse("admin:orders_order_set_status", args=[obj.id, status])
            label = labels.get(status, status)

            if status == Order.Status.CANCELED:
                bg, fg, border = "#fce8e6", "#c5221f", "#f3b7b2"
            elif status == Order.Status.DONE:
                bg, fg, border = "#e6f4ea", "#137333", "#b7dfc0"
            elif status == Order.Status.COOKING:
                bg, fg, border = "#fff4e5", "#b06000", "#f0d0a0"
            else:
                bg, fg, border = "#e8f0fe", "#174ea6", "#bfd3fb"

            buttons.append(
                format_html(
                    '<button type="submit" formaction="{}" formmethod="post" '
                    'style="display:inline-flex;align-items:center;justify-content:center;'
                    'padding:8px 12px;margin:0 8px 8px 0;border-radius:10px;'
                    'background:{};color:{};border:1px solid {};font-weight:700;cursor:pointer;">{}</button>',
                    url,
                    bg,
                    fg,
                    border,
                    label,
                )
            )

        return format_html_join("", "{}", ((btn,) for btn in buttons))

        # return mark_safe("".join(buttons))

    status_controls.short_description = "Быстрые действия"

    def status_badge(self, obj):
        label = obj.get_status_display()

        color_map = {
            Order.Status.NEW: ("#e8f0fe", "#174ea6"),
            Order.Status.CONFIRMED: ("#e6f4ea", "#137333"),
            Order.Status.COOKING: ("#fff4e5", "#b06000"),
            Order.Status.ON_THE_WAY: ("#e8f0fe", "#0b57d0"),
            Order.Status.DONE: ("#e6f4ea", "#137333"),
            Order.Status.CANCELED: ("#fce8e6", "#c5221f"),
        }
        bg, fg = color_map.get(obj.status, ("#f3f3f3", "#111"))

        return format_html(
            '<span data-order-status="{}" style="display:inline-block;padding:4px 10px;border-radius:999px;background:{};color:{};font-weight:700;">{}</span>',
            obj.status,
            bg,
            fg,
            label,
        )

    status_badge.short_description = "Статус"

    def short_items(self, obj):
        items = list(obj.items.all()[:3])
        if not items:
            return "—"

        parts = [f"{item.product_name} × {item.quantity}" for item in items]
        total_count = len(obj.items.all())
        if total_count > 3:
            parts.append(f"... ещё {total_count - 3}")

        return "; ".join(parts)

    short_items.short_description = "Состав"

    def short_address(self, obj):
        if obj.fulfillment == Order.Fulfillment.PICKUP:
            return "Самовывоз"

        if not obj.address_line:
            return "—"

        parts = [obj.address_line]
        extra = []

        if obj.address_entrance:
            extra.append(f"пд. {obj.address_entrance}")
        if obj.address_floor:
            extra.append(f"эт. {obj.address_floor}")
        if obj.address_apartment:
            extra.append(f"кв/оф. {obj.address_apartment}")

        if extra:
            parts.append(f"({', '.join(extra)})")

        return " ".join(parts)

    short_address.short_description = "Адрес"

    def public_link(self, obj):
        url = reverse("orders:order_status", kwargs={"public_id": obj.public_id})
        return format_html('<a href="{}" target="_blank">открыть</a>', url)

    public_link.short_description = "Публичная ссылка"


    def changelist_view(self, request, extra_context=None):

        today = timezone.localdate()

        qs = Order.objects.all()

        new_orders = qs.filter(status=Order.Status.NEW).count()

        active_orders = qs.exclude(
            status__in=[Order.Status.DONE, Order.Status.CANCELED]
        ).count()

        done_today = qs.filter(
            status=Order.Status.DONE,
            created_at__date=today,
        ).count()

        revenue_today = qs.filter(
            status=Order.Status.DONE,
            created_at__date=today,
        ).aggregate(total=Sum("total"))["total"] or 0

        extra_context = extra_context or {}

        extra_context["order_dashboard"] = {
            "new": new_orders,
            "active": active_orders,
            "done_today": done_today,
            "revenue_today": revenue_today,
        }

        latest = qs.order_by("-updated_at", "-id").first()

        extra_context["order_live"] = {
            "summary_url": reverse("admin:orders_order_live_summary"),
            "latest_order_id": latest.id if latest else "",
            "latest_updated_at": latest.updated_at.isoformat() if latest else "",
        }

        return super().changelist_view(request, extra_context=extra_context)


    def live_summary_view(self, request):
        latest = Order.objects.order_by("-updated_at", "-id").first()

        today = timezone.localdate()
        qs = Order.objects.all()

        payload = {
            "latest_order_id": latest.id if latest else None,
            "latest_updated_at": latest.updated_at.isoformat() if latest else None,
            "new_count": qs.filter(status=Order.Status.NEW).count(),
            "active_count": qs.exclude(
                status__in=[Order.Status.DONE, Order.Status.CANCELED]
            ).count(),
            "done_today": qs.filter(
                status=Order.Status.DONE,
                created_at__date=today,
            ).count(),
            "revenue_today": str(
                qs.filter(
                    status=Order.Status.DONE,
                    created_at__date=today,
                ).aggregate(total=Sum("total"))["total"] or 0
            ),
        }

        return JsonResponse(payload)
    

    # def change_view(self, request, object_id, form_url="", extra_context=None):
    #     self._status_controls_csrf_token = get_token(request)
    #     return super().change_view(request, object_id, form_url, extra_context)
    