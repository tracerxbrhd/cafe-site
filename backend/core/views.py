from django.shortcuts import render
from .models import BusinessLunchWeek, BusinessLunchDay, ServicePage
from .utils import get_current_business_lunch_day, get_service_page


def business_lunches_page(request):
    current_day = get_current_business_lunch_day()

    weeks = (
        BusinessLunchWeek.objects.filter(
            is_active=True,
            is_published=True,
        )
        .prefetch_related("days__items__product")
        .order_by("-week_start")
    )

    return render(
        request,
        "core/business_lunches.html",
        {
            "current_day": current_day,
            "weeks": weeks,
        },
    )


def banquets_page(request):
    page = get_service_page(ServicePage.PageType.BANQUETS)
    return render(request, "core/service_page.html", {"page": page, "page_kind": "banquets"})


def catering_page(request):
    page = get_service_page(ServicePage.PageType.CATERING)
    return render(request, "core/service_page.html", {"page": page, "page_kind": "catering"})