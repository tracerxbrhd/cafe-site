from django.contrib import admin, messages
from django.urls import reverse
from django.utils.html import format_html

from .models import Order, OrderItem
from .services import sync_order_telegram_message


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ("line_total",)


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


@admin.action(description="Перевести в «Подтверждён»")
def mark_confirmed(modeladmin, request, queryset):
    _apply_status_transition(modeladmin, request, queryset, Order.Status.CONFIRMED, "Подтверждён")


@admin.action(description="Перевести в «Готовится»")
def mark_cooking(modeladmin, request, queryset):
    _apply_status_transition(modeladmin, request, queryset, Order.Status.COOKING, "Готовится")


@admin.action(description="Перевести в «В пути»")
def mark_on_the_way(modeladmin, request, queryset):
    _apply_status_transition(modeladmin, request, queryset, Order.Status.ON_THE_WAY, "В пути")


@admin.action(description="Перевести в «Выполнен»")
def mark_done(modeladmin, request, queryset):
    _apply_status_transition(modeladmin, request, queryset, Order.Status.DONE, "Выполнен")


@admin.action(description="Перевести в «Отменён»")
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
        "total",
        "created_at",
        "public_link",
    )
    list_filter = ("status", "fulfillment", "created_at")
    search_fields = ("id", "customer_name", "customer_phone", "public_id")
    readonly_fields = (
        "public_id",
        "total",
        "created_at",
        "updated_at",
        "telegram_chat_id",
        "telegram_message_id",
    )
    inlines = [OrderItemInline]
    actions = [mark_confirmed, mark_cooking, mark_on_the_way, mark_done, mark_canceled]

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
            '<span style="display:inline-block;padding:4px 10px;border-radius:999px;background:{};color:{};font-weight:700;">{}</span>',
            bg,
            fg,
            label,
        )

    status_badge.short_description = "Статус"

    def public_link(self, obj):
        url = reverse("orders:order_status", kwargs={"public_id": obj.public_id})
        return format_html('<a href="{}" target="_blank">открыть</a>', url)

    public_link.short_description = "Публичная ссылка"