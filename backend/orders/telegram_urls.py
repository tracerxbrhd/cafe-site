from django.urls import path
from . import telegram_views

urlpatterns = [
    path("webhook/<str:secret>/", telegram_views.telegram_webhook, name="telegram_webhook"),
]