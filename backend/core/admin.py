from django.contrib import admin
from .models import CafeSettings


@admin.register(CafeSettings)
class CafeSettingsAdmin(admin.ModelAdmin):
    list_display = ("is_open", "phone", "working_hours_text", "min_order_amount", "delivery_fee", "updated_at")

    def has_add_permission(self, request):
        # одна запись достаточно
        if CafeSettings.objects.exists():
            return False
        return super().has_add_permission(request)