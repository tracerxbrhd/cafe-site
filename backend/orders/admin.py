from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html
from .models import Order, OrderItem


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ("line_total",)


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ("id", "status", "fulfillment", "customer_name", "customer_phone", "total", "created_at")
    list_filter = ("status", "fulfillment", "created_at")
    search_fields = ("id", "customer_name", "customer_phone")
    readonly_fields = ("total", "created_at", "updated_at")
    inlines = [OrderItemInline]

    def public_link(self, obj):
        url = reverse("orders:order_status", kwargs={"public_id": obj.public_id})
        return format_html('<a href="{}" target="_blank">открыть</a>', url)
    public_link.short_description = "Публичная ссылка"