from __future__ import annotations

from django.contrib.sitemaps import Sitemap
from django.urls import reverse

from catalog.models import Category, Product

from .models import BusinessLunchWeek, ServicePage


class StaticViewSitemap(Sitemap):
    priority = 0.9
    changefreq = "weekly"

    def items(self):
        return [
            "catalog:index",
            "core:business_lunches",
            "core:banquets",
            "core:catering",
        ]

    def location(self, item):
        return reverse(item)

    def lastmod(self, item):
        if item == "catalog:index":
            return (
                Product.objects.filter(is_active=True, category__is_active=True)
                .order_by("-updated_at")
                .values_list("updated_at", flat=True)
                .first()
            )
        if item == "core:business_lunches":
            return (
                BusinessLunchWeek.objects.filter(is_active=True, is_published=True)
                .order_by("-updated_at")
                .values_list("updated_at", flat=True)
                .first()
            )
        page_type = {
            "core:banquets": ServicePage.PageType.BANQUETS,
            "core:catering": ServicePage.PageType.CATERING,
        }.get(item)
        if page_type:
            return (
                ServicePage.objects.filter(page_type=page_type, is_published=True)
                .order_by("-updated_at")
                .values_list("updated_at", flat=True)
                .first()
            )
        return None


class CategorySitemap(Sitemap):
    priority = 0.7
    changefreq = "weekly"

    def items(self):
        return Category.objects.filter(is_active=True).order_by("sort_order", "name")

    def location(self, obj: Category):
        return reverse("catalog:category_detail", kwargs={"slug": obj.slug})


class ProductSitemap(Sitemap):
    priority = 0.8
    changefreq = "weekly"

    def items(self):
        return (
            Product.objects.filter(is_active=True, category__is_active=True)
            .select_related("category")
            .order_by("category__sort_order", "category__name", "sort_order", "name")
        )

    def lastmod(self, obj: Product):
        return obj.updated_at

    def location(self, obj: Product):
        return reverse("catalog:product_detail", kwargs={"slug": obj.slug})
