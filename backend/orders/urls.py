from django.urls import path
from . import views

app_name = "orders"

urlpatterns = [
    path("", views.cart_page, name="cart"),
    path("my-orders/", views.order_lookup_page, name="order_lookup"),
    path("checkout/", views.checkout_page, name="checkout"),

    path("success/<uuid:public_id>/", views.order_success_page, name="order_success"),

    path("order/<uuid:public_id>/", views.order_status_page, name="order_status"),
    path("api/order/<uuid:public_id>/", views.order_api_status, name="api_order_status"),

    path("api/add/", views.cart_api_add, name="api_add"),
    path("api/add-business-lunch/", views.cart_api_add_business_lunch, name="api_add_business_lunch"),
    path("api/set/", views.cart_api_set, name="api_set"),
    path("api/clear/", views.cart_api_clear, name="api_clear"),
    path("api/summary/", views.cart_api_summary, name="api_summary"),
    path("api/apply-promo/", views.checkout_api_apply_promo, name="api_apply_promo"),
    path("api/delivery-quote/", views.delivery_api_quote, name="api_delivery_quote"),
]
