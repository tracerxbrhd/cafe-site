from django.contrib import admin
from .models import CafeSettings, DeliveryZone


@admin.register(CafeSettings)
class CafeSettingsAdmin(admin.ModelAdmin):
    list_display = (
        "is_open",
        "phone",
        "working_hours_text",
        "min_order_amount",
        "delivery_fee",
        "updated_at",
    )

    def has_add_permission(self, request):
        if CafeSettings.objects.exists():
            return False
        return super().has_add_permission(request)


@admin.register(DeliveryZone)
class DeliveryZoneAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "code",
        "is_active",
        "delivery_fee",
        "min_order_amount",
        "sort_order",
    )
    list_filter = ("is_active",)
    search_fields = ("name", "code")
    ordering = ("sort_order", "name")
    prepopulated_fields = {"code": ("name",)}