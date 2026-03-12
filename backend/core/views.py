from django.shortcuts import render
from .models import BusinessLunchMenu
from .utils import get_current_business_lunch_menu


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
    return render(request, "core/banquets.html")


def catering_page(request):
    return render(request, "core/catering.html")