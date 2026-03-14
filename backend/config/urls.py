from django.conf import settings
from django.conf.urls.static import static
from django.contrib.sitemaps.views import sitemap
from django.db import connections
from django.db.utils import OperationalError
from django.contrib import admin
from django.http import JsonResponse
from django.urls import include, path

from core.sitemaps import CategorySitemap, ProductSitemap, StaticViewSitemap
from core.views import robots_txt


sitemaps = {
    "static": StaticViewSitemap,
    "categories": CategorySitemap,
    "products": ProductSitemap,
}


def healthz(request):
    try:
        with connections["default"].cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
    except OperationalError:
        return JsonResponse({"ok": False, "database": "unavailable"}, status=503)

    return JsonResponse({"ok": True, "database": "available"})


urlpatterns = [
    path("admin/", admin.site.urls),
    path("healthz/", healthz, name="healthz"),
    path("robots.txt", robots_txt, name="robots_txt"),
    path("sitemap.xml", sitemap, {"sitemaps": sitemaps}, name="sitemap"),
    path("", include("catalog.urls")),
    path("pages/", include("core.urls")),
    path("cart/", include("orders.urls")),
    path("telegram/", include("orders.telegram_urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
