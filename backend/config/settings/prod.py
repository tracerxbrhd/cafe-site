import os

from django.core.exceptions import ImproperlyConfigured

from .base import *  # noqa


DEBUG = False

if SECRET_KEY in {"dev", "dev-secret-key", "change_me"}:
    raise ImproperlyConfigured("DJANGO_SECRET_KEY must be set in production.")

if not ALLOWED_HOSTS:
    raise ImproperlyConfigured("DJANGO_ALLOWED_HOSTS must be set in production.")

SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
USE_X_FORWARDED_HOST = env_bool("DJANGO_USE_X_FORWARDED_HOST", True)

SECURE_SSL_REDIRECT = env_bool("DJANGO_SECURE_SSL_REDIRECT", False)
SESSION_COOKIE_SECURE = env_bool("DJANGO_SESSION_COOKIE_SECURE", SECURE_SSL_REDIRECT)
CSRF_COOKIE_SECURE = env_bool("DJANGO_CSRF_COOKIE_SECURE", SECURE_SSL_REDIRECT)

SECURE_HSTS_SECONDS = int(os.getenv("DJANGO_SECURE_HSTS_SECONDS", "0"))
SECURE_HSTS_INCLUDE_SUBDOMAINS = env_bool(
    "DJANGO_SECURE_HSTS_INCLUDE_SUBDOMAINS",
    False,
)
SECURE_HSTS_PRELOAD = env_bool("DJANGO_SECURE_HSTS_PRELOAD", False)

SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = os.getenv("DJANGO_SECURE_REFERRER_POLICY", "same-origin")
X_FRAME_OPTIONS = os.getenv("DJANGO_X_FRAME_OPTIONS", "DENY")

CSRF_COOKIE_HTTPONLY = env_bool("DJANGO_CSRF_COOKIE_HTTPONLY", False)
SESSION_COOKIE_HTTPONLY = env_bool("DJANGO_SESSION_COOKIE_HTTPONLY", True)
