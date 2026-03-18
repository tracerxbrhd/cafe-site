import json
from urllib.parse import urljoin

from django.conf import settings

from .utils import get_cafe_settings


def _origin(request) -> str:
    if settings.SITE_URL:
        return settings.SITE_URL.rstrip("/")
    return request.build_absolute_uri("/").rstrip("/")


def _absolute_url(origin: str, path_or_url: str) -> str:
    if not path_or_url:
        return ""
    if path_or_url.startswith(("http://", "https://")):
        return path_or_url
    return urljoin(f"{origin}/", path_or_url.lstrip("/"))


def site_meta(request):
    origin = _origin(request)
    canonical_url = urljoin(f"{origin}/", request.path.lstrip("/"))
    default_image_url = _absolute_url(origin, settings.SEO_DEFAULT_OG_IMAGE)

    cafe = get_cafe_settings()
    restaurant_schema = {
        "@context": "https://schema.org",
        "@type": "Restaurant",
        "name": settings.SITE_NAME,
        "url": origin,
    }
    if settings.SEO_DEFAULT_DESCRIPTION:
        restaurant_schema["description"] = settings.SEO_DEFAULT_DESCRIPTION
    if default_image_url:
        restaurant_schema["image"] = default_image_url
    if cafe and cafe.phone:
        restaurant_schema["telephone"] = cafe.phone
    if cafe and cafe.address_text:
        restaurant_schema["address"] = {
            "@type": "PostalAddress",
            "streetAddress": cafe.address_text,
            "addressLocality": "Ижевск",
            "addressCountry": "RU",
        }

    return {
        "site_name": settings.SITE_NAME,
        "site_url": settings.SITE_URL,
        "seo_origin": origin,
        "seo_canonical_url": canonical_url,
        "seo_default_description": settings.SEO_DEFAULT_DESCRIPTION,
        "seo_default_image_url": default_image_url,
        "google_tag_id": settings.GOOGLE_TAG_ID,
        "yandex_metrika_counter_id": settings.YANDEX_METRIKA_COUNTER_ID,
        "google_site_verification": settings.GOOGLE_SITE_VERIFICATION,
        "yandex_verification": settings.YANDEX_VERIFICATION,
        "seo_restaurant_schema": json.dumps(restaurant_schema, ensure_ascii=False),
    }


def cafe_settings(request):
    settings = get_cafe_settings()

    return {
        "cafe_settings": settings,
        "cafe_is_open_now": settings.is_currently_open() if settings else True,
        "cafe_is_accepting_orders_now": settings.is_accepting_orders_now() if settings else True,
    }
