from django.shortcuts import get_object_or_404, render

from orders.cart import CART_SESSION_KEY
from .models import Category, Product
from promotions.models import PromoBanner

from core.utils import get_current_business_lunch_menu


PREVIEW_PRODUCTS_PER_CATEGORY = 4


def _get_cart_map(request):
    cart = request.session.get(CART_SESSION_KEY) or {}
    try:
        return {int(k): int(v) for k, v in cart.items()}
    except Exception:
        return {}


def catalog_index(request):
    categories = list(
        Category.objects.filter(is_active=True)
        .order_by("sort_order", "name")
    )

    products = list(
        Product.objects.filter(is_active=True, category__is_active=True)
        .select_related("category")
        .prefetch_related("images")
        .order_by("category__sort_order", "category__name", "sort_order", "name")
    )

    products_by_category = {category.id: [] for category in categories}
    for product in products:
        products_by_category.setdefault(product.category_id, []).append(product)

    preview_sections = []
    for category in categories:
        items = products_by_category.get(category.id, [])
        if not items:
            continue

        preview_sections.append(
            {
                "category": category,
                "products": items[:PREVIEW_PRODUCTS_PER_CATEGORY],
                "total_products": len(items),
                "has_more": len(items) > PREVIEW_PRODUCTS_PER_CATEGORY,
            }
        )

    banners = list(
    PromoBanner.objects.filter(is_active=True)
    .order_by("sort_order", "-created_at", "id")
    )

    current_business_lunch_menu = get_current_business_lunch_menu()

    return render(
        request,
        "catalog/index.html",
        {
            "categories": [section["category"] for section in preview_sections],
            "preview_sections": preview_sections,
            "cart_map": _get_cart_map(request),
            "banners": banners,
            "current_business_lunch_menu": current_business_lunch_menu,
        },
    )


def category_detail(request, slug: str):
    category = get_object_or_404(Category, slug=slug, is_active=True)

    products = list(
        Product.objects.filter(
            is_active=True,
            category=category,
            category__is_active=True,
        )
        .select_related("category")
        .prefetch_related("images")
        .order_by("sort_order", "name")
    )

    return render(
        request,
        "catalog/category_detail.html",
        {
            "category": category,
            "products": products,
            "cart_map": _get_cart_map(request),
        },
    )


def product_detail(request, slug: str):
    product = get_object_or_404(
        Product.objects.select_related("category").prefetch_related("images"),
        slug=slug,
        is_active=True,
        category__is_active=True,
    )
    cart = request.session.get(CART_SESSION_KEY) or {}
    qty = int(cart.get(str(product.id), 0) or 0)
    return render(request, "catalog/product_detail.html", {"product": product, "qty": qty})