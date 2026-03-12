from django.contrib import admin
from .models import CafeSettings, DeliveryZone, BusinessLunchMenu, BusinessLunchItem, ServicePage


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


class BusinessLunchItemInline(admin.TabularInline):
    model = BusinessLunchItem
    extra = 1
    fields = ("name", "description", "price", "image", "sort_order")


@admin.register(BusinessLunchMenu)
class BusinessLunchMenuAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "week_start",
        "week_end",
        "is_active",
        "is_published",
        "sort_order",
    )
    list_filter = ("is_active", "is_published", "week_start", "week_end")
    search_fields = ("title", "description")
    ordering = ("-week_start", "sort_order")
    prepopulated_fields = {"slug": ("title",)}
    inlines = [BusinessLunchItemInline]


@admin.register(ServicePage)
class ServicePageAdmin(admin.ModelAdmin):
    list_display = ("page_type", "title", "is_published", "updated_at")
    list_filter = ("page_type", "is_published")
    search_fields = ("title", "subtitle", "content", "features", "cta_title", "cta_text")