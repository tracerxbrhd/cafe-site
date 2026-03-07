# from django.contrib import admin
# from .models import Category, Product, ProductImage


# @admin.register(Category)
# class CategoryAdmin(admin.ModelAdmin):
#     list_display = ("name", "slug", "is_active", "sort_order")
#     list_filter = ("is_active",)
#     search_fields = ("name", "slug")
#     prepopulated_fields = {"slug": ("name",)}
#     ordering = ("sort_order", "name")


# class ProductImageInline(admin.TabularInline):
#     model = ProductImage
#     extra = 0


# @admin.register(Product)
# class ProductAdmin(admin.ModelAdmin):
#     list_display = ("name", "category", "price", "is_active", "sort_order", "updated_at")
#     list_filter = ("is_active", "category")
#     search_fields = ("name", "slug")
#     prepopulated_fields = {"slug": ("name",)}
#     ordering = ("sort_order", "name")
#     inlines = [ProductImageInline]
from django.contrib import admin
from .models import Category, Product, ProductImage
from django.utils.html import format_html


class ProductImageInline(admin.TabularInline):
    model = ProductImage
    extra = 1
    fields = (
        "image",
        "alt_text",
        "is_main",
        "sort_order",
    )


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):

    def main_image_preview(self, obj):
        image = obj.main_image
        if not image:
            return "—"
        return format_html(
            '<img src="{}" style="height:40px;border-radius:4px;" />',
            image.image.url
        )

    list_display = (
        "main_image_preview",
        "name",
        "category",
        "price",
        "is_active",
        "sort_order",
    )

    list_editable = (
    "is_active",
    "sort_order",
    )

    list_filter = (
        "category",
        "is_active",
    )

    search_fields = (
        "name",
        "description",
    )

    ordering = (
        "category",
        "sort_order",
        "name",
    )

    prepopulated_fields = {
        "slug": ("name",)
    }

    inlines = [ProductImageInline]

    main_image_preview.short_description = "Фото"


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):

    list_display = (
        "name",
        "is_active",
        "sort_order",
    )

    ordering = (
        "sort_order",
        "name",
    )

    prepopulated_fields = {
        "slug": ("name",)
    }


@admin.register(ProductImage)
class ProductImageAdmin(admin.ModelAdmin):

    list_display = (
        "product",
        "is_main",
        "sort_order",
    )

    list_filter = (
        "is_main",
    )

    ordering = (
        "product",
        "sort_order",
    )