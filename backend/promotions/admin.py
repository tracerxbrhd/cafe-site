from django.contrib import admin
from .models import PromoBanner, PromoCode


@admin.register(PromoBanner)
class PromoBannerAdmin(admin.ModelAdmin):
    list_display = ("title", "is_active", "sort_order", "created_at")
    list_filter = ("is_active", "created_at")
    search_fields = ("title", "subtitle", "button_text", "button_url")
    ordering = ("sort_order", "-created_at")


@admin.register(PromoCode)
class PromoCodeAdmin(admin.ModelAdmin):
    list_display = (
        "code",
        "discount_type",
        "discount_value",
        "valid_until",
        "is_active",
        "updated_at",
    )
    list_filter = ("discount_type", "is_active", "valid_until")
    search_fields = ("code",)
    ordering = ("code",)
    readonly_fields = ("created_at", "updated_at")
    fieldsets = (
        (
            "Основное",
            {
                "fields": (
                    "code",
                    "discount_type",
                    "discount_value",
                    "valid_until",
                    "is_active",
                )
            },
        ),
        (
            "Системное",
            {
                "classes": ("collapse",),
                "fields": ("created_at", "updated_at"),
            },
        ),
    )
