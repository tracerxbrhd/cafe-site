from django.urls import path
from . import views

app_name = "core"

urlpatterns = [
    path("business-lunches/", views.business_lunches_page, name="business_lunches"),
    path("banquets/", views.banquets_page, name="banquets"),
    path("catering/", views.catering_page, name="catering"),
    path("children-parties/", views.children_parties_page, name="children_parties"),
]
