from django.shortcuts import render
from .models import BusinessLunchMenu, ServicePage
from .utils import get_current_business_lunch_menu, get_service_page


def business_lunches_page(request):
    current_menu = get_current_business_lunch_menu()
    archive_menus = (
        BusinessLunchMenu.objects.filter(is_active=True, is_published=True)
        .prefetch_related("items")
        .order_by("-week_start", "sort_order", "-id")
    )

    return render(
        request,
        "core/business_lunches.html",
        {
            "current_menu": current_menu,
            "archive_menus": archive_menus,
        },
    )


def banquets_page(request):
    page = get_service_page(ServicePage.PageType.BANQUETS)
    return render(request, "core/service_page.html", {"page": page, "page_kind": "banquets"})


def catering_page(request):
    page = get_service_page(ServicePage.PageType.CATERING)
    return render(request, "core/service_page.html", {"page": page, "page_kind": "catering"})