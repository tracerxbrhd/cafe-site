from datetime import date, time
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse

from core.models import BusinessLunchDay, BusinessLunchWeek, CafeSettings

from .cart import LUNCH_CART_SESSION_KEY
from .models import Order, OrderItem


class CheckoutBusinessLunchTests(TestCase):
    def setUp(self):
        CafeSettings.objects.create(
            is_open=True,
            opening_time=time(0, 0),
            closing_time=time(0, 0),
            min_order_amount=Decimal("0.00"),
        )
        week = BusinessLunchWeek.objects.create(
            title="Тестовая неделя",
            slug="test-week",
            week_start=date(2026, 3, 9),
            week_end=date(2026, 3, 15),
            is_active=True,
            is_published=True,
        )
        self.lunch_day = BusinessLunchDay.objects.create(
            week=week,
            service_date=date(2026, 3, 14),
            title="Субботний набор",
            price=Decimal("450.00"),
            is_active=True,
        )

    def _set_lunch_in_session(self, qty=1):
        session = self.client.session
        session[LUNCH_CART_SESSION_KEY] = {str(self.lunch_day.id): qty}
        session.save()

    def test_checkout_page_shows_business_lunch_name(self):
        self._set_lunch_in_session()

        response = self.client.get(reverse("orders:checkout"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.lunch_day.display_name)

    def test_checkout_creates_order_item_for_business_lunch(self):
        self._set_lunch_in_session()

        response = self.client.post(
            reverse("orders:checkout"),
            data={
                "fulfillment": Order.Fulfillment.PICKUP,
                "customer_name": "Иван",
                "customer_phone": "+7 (900) 123-45-67",
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(Order.objects.count(), 1)
        self.assertEqual(OrderItem.objects.count(), 1)

        order = Order.objects.get()
        item = OrderItem.objects.get()

        self.assertEqual(item.lunch_day, self.lunch_day)
        self.assertIsNone(item.product)
        self.assertEqual(item.product_name, self.lunch_day.display_name)
        self.assertEqual(item.quantity, 1)
        self.assertEqual(item.unit_price, self.lunch_day.price)
        self.assertEqual(item.line_total, self.lunch_day.price)
        self.assertEqual(order.total, self.lunch_day.price)
        self.assertNotIn(LUNCH_CART_SESSION_KEY, self.client.session)


class OrderLookupTests(TestCase):
    def setUp(self):
        CafeSettings.objects.create(
            is_open=True,
            opening_time=time(0, 0),
            closing_time=time(0, 0),
            min_order_amount=Decimal("0.00"),
        )
        self.phone = "+79001234567"
        self.active_order = Order.objects.create(
            status=Order.Status.CONFIRMED,
            fulfillment=Order.Fulfillment.PICKUP,
            customer_name="Иван",
            customer_phone=self.phone,
            total=Decimal("650.00"),
        )
        self.done_order = Order.objects.create(
            status=Order.Status.DONE,
            fulfillment=Order.Fulfillment.DELIVERY,
            customer_name="Иван",
            customer_phone=self.phone,
            total=Decimal("980.00"),
        )

    def test_lookup_by_public_id_shows_order(self):
        response = self.client.get(
            reverse("orders:order_lookup"),
            {"lookup": "public_id", "public_id": str(self.active_order.public_id)},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, f"Заказ #{self.active_order.id}")
        self.assertContains(response, str(self.active_order.public_id))

    def test_lookup_by_phone_shows_active_and_completed_orders(self):
        response = self.client.get(
            reverse("orders:order_lookup"),
            {"lookup": "phone", "phone": "+7 (900) 123-45-67"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Актуальные заказы")
        self.assertContains(response, "Завершённые и закрытые заказы")
        self.assertContains(response, f"Заказ #{self.active_order.id}")
        self.assertContains(response, f"Заказ #{self.done_order.id}")

    def test_order_success_page_contains_public_id(self):
        response = self.client.get(
            reverse("orders:order_success", kwargs={"public_id": self.active_order.public_id})
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Идентификатор заказа")
        self.assertContains(response, str(self.active_order.public_id))
