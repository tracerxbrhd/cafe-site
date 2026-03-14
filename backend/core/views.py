from django.conf import settings
from django.http import HttpResponse
from django.shortcuts import render
from django.urls import reverse
from .models import BusinessLunchWeek, BusinessLunchDay, ServicePage
from .utils import get_current_business_lunch_day, get_service_page
from orders.cart import lunch_get_qty


def business_lunches_page(request):
    current_day = get_current_business_lunch_day()

    if current_day:
        current_day.cart_qty = lunch_get_qty(request.session, current_day.id)

    weeks = (
        BusinessLunchWeek.objects.filter(
            is_active=True,
            is_published=True,
        )
        .prefetch_related("days__items__product")
        .order_by("-week_start")
    )

    for week in weeks:
        for day in week.days.all():
            day.cart_qty = lunch_get_qty(request.session, day.id)

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


def robots_txt(request):
    origin = settings.SITE_URL.rstrip("/") if settings.SITE_URL else request.build_absolute_uri("/").rstrip("/")
    sitemap_url = f"{origin}{reverse('sitemap')}"
    lines = [
        "User-agent: *",
        "Allow: /",
        "Disallow: /admin/",
        "Disallow: /telegram/",
        "Disallow: /cart/api/",
        "Disallow: /healthz/",
        f"Sitemap: {sitemap_url}",
    ]
    return HttpResponse("\n".join(lines), content_type="text/plain; charset=utf-8")
