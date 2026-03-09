from urllib.parse import urlencode

from django.contrib import admin, messages
from django.http import HttpResponseRedirect
from django.urls import path, reverse
from django.utils.html import format_html, format_html_join
from django.db.models import Case, IntegerField, Value, When, Sum
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
    
    def has_change_permission(self, request, obj=None):
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
        "fulfillment_badge",
        "customer_name",
        "customer_phone",
        "short_items",
        "short_address",
        "short_comment",
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
        "customer_comment",
    )
    # readonly_fields = (
    #     "public_id",
    #     "total",
    #     "created_at",
    #     "updated_at",
    #     "telegram_chat_id",
    #     "telegram_message_id",
    #     "status_controls",
    # )
    # ordering = ("-created_at",)
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
        qs = super().get_queryset(request).prefetch_related("items")

        return qs.annotate(
            status_priority=Case(
                When(status=Order.Status.NEW, then=Value(0)),
                When(status=Order.Status.CONFIRMED, then=Value(1)),
                When(status=Order.Status.COOKING, then=Value(2)),
                When(status=Order.Status.ON_THE_WAY, then=Value(3)),
                When(status=Order.Status.DONE, then=Value(4)),
                When(status=Order.Status.CANCELED, then=Value(5)),
                default=Value(99),
                output_field=IntegerField(),
            )
        ).order_by("status_priority", "-created_at", "-id")

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

        if not self.has_change_permission(request, obj=order):
            self.message_user(request, "Недостаточно прав для изменения заказа.", level=messages.ERROR)
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

    def fulfillment_badge(self, obj):
        if obj.fulfillment == Order.Fulfillment.PICKUP:
            bg, fg = "#f1f3f4", "#111"
            label = "Самовывоз"
        else:
            bg, fg = "#eef4ff", "#0b57d0"
            label = "Доставка"

        return format_html(
            '<span style="display:inline-block;padding:4px 10px;border-radius:999px;background:{};color:{};font-weight:700;">{}</span>',
            bg,
            fg,
            label,
        )

    fulfillment_badge.short_description = "Получение"

    def short_items(self, obj):
        items = list(obj.items.all())
        if not items:
            return "—"

        visible = items[:3]
        parts = [f"{item.product_name} × {item.quantity}" for item in visible]

        if len(items) > 3:
            parts.append(f"... ещё {len(items) - 3}")

        return format_html("<div style='max-width:320px;line-height:1.45;'>{}</div>", "; ".join(parts))

    short_items.short_description = "Состав"

    def short_address(self, obj):
        if obj.fulfillment == Order.Fulfillment.PICKUP:
            # return format_html("{}", "<span style='color:#666;'>Самовывоз</span>")
            return mark_safe("<span style='color:#666;'>Самовывоз</span>")

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

        text = " ".join(parts)
        if extra:
            text += f" ({', '.join(extra)})"

        return format_html("<div style='max-width:260px;line-height:1.4;'>{}</div>", text)
    
    short_address.short_description = "Адрес"

    def short_comment(self, obj):
        if not obj.customer_comment:
            return "—"

        text = obj.customer_comment.strip()
        if len(text) > 80:
            text = text[:77] + "..."

        return format_html(
            "<div style='max-width:220px;line-height:1.4;color:#444;'>{}</div>",
            text,
        )

    short_comment.short_description = "Комментарий"

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

        cooking_orders = qs.filter(status=Order.Status.COOKING).count()
        on_the_way_orders = qs.filter(status=Order.Status.ON_THE_WAY).count()

        latest = qs.order_by("-updated_at", "-id").first()

        changelist_url = reverse("admin:orders_order_changelist")

        extra_context = extra_context or {}
        extra_context["order_dashboard"] = {
            "new": new_orders,
            "active": active_orders,
            "done_today": done_today,
            "revenue_today": revenue_today,
        }
        extra_context["order_attention"] = [
            {
                "title": "Новые",
                "count": new_orders,
                "bg": "#e8f0fe",
                "fg": "#174ea6",
                "url": f"{changelist_url}?status__exact={Order.Status.NEW}",
            },
            {
                "title": "Готовятся",
                "count": cooking_orders,
                "bg": "#fff4e5",
                "fg": "#b06000",
                "url": f"{changelist_url}?status__exact={Order.Status.COOKING}",
            },
            {
                "title": "В пути",
                "count": on_the_way_orders,
                "bg": "#eef4ff",
                "fg": "#0b57d0",
                "url": f"{changelist_url}?status__exact={Order.Status.ON_THE_WAY}",
            },
            {
                "title": "Все активные",
                "count": active_orders,
                "bg": "#f1f3f4",
                "fg": "#111",
                "url": f"{changelist_url}?activity=active",
            },
        ]
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

    def has_add_permission(self, request):
        return request.user.is_superuser


    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser
    

    def get_readonly_fields(self, request, obj=None):
        base_readonly = [
            "public_id",
            "total",
            "created_at",
            "updated_at",
            "telegram_chat_id",
            "telegram_message_id",
            "status_controls",
        ]

        if request.user.is_superuser:
            return base_readonly

        return base_readonly + [
            "status",
            "fulfillment",
            "customer_name",
            "customer_phone",
            "customer_comment",
            "address_line",
            "address_entrance",
            "address_floor",
            "address_apartment",
        ]
    
    def get_actions(self, request):
        actions = super().get_actions(request)

        if request.user.is_superuser:
            return actions

        return {}