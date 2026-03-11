from .utils import get_cafe_settings


def cafe_settings(request):
    settings = get_cafe_settings()

    return {
        "cafe_settings": settings,
        "cafe_is_open_now": settings.is_currently_open() if settings else True,
    }