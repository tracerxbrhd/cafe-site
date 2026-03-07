from django.urls import path
from . import views

app_name = "catalog"

urlpatterns = [
    path("", views.catalog_index, name="index"),
    path("category/<slug:slug>/", views.category_detail, name="category_detail"),
    path("p/<slug:slug>/", views.product_detail, name="product_detail"),
]