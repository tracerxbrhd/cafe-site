from django.contrib import admin
from .models import PromoBanner


@admin.register(PromoBanner)
class PromoBannerAdmin(admin.ModelAdmin):
    list_display = ("title", "is_active", "sort_order", "created_at")
    list_filter = ("is_active", "created_at")
    search_fields = ("title", "subtitle", "button_text", "button_url")
    ordering = ("sort_order", "-created_at")