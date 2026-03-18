from datetime import date, datetime, time
from decimal import Decimal
import os
from unittest.mock import patch

from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from core.models import BusinessLunchDay, BusinessLunchWeek, CafeSettings
from promotions.models import PromoCode

from .cart import LUNCH_CART_SESSION_KEY
from .models import OnlinePaymentAttempt, Order, OrderItem
from .telegram_handlers import process_telegram_update
from .yookassa import YooKassaPayment


class CheckoutBusinessLunchTests(TestCase):
    def setUp(self):
        CafeSettings.objects.create(
            is_open=True,
            opening_time=time(0, 0),
            closing_time=time(0, 0),
            order_opening_time=time(0, 0),
            order_closing_time=time(0, 0),
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
                "payment_method": Order.PaymentMethod.UPON_RECEIPT,
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
            order_opening_time=time(0, 0),
            order_closing_time=time(0, 0),
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
        OrderItem.objects.create(
            order=self.active_order,
            product=None,
            product_name="Борщ",
            unit_price=Decimal("320.00"),
            quantity=2,
            line_total=Decimal("640.00"),
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

    def test_order_status_page_shows_order_items(self):
        response = self.client.get(
            reverse("orders:order_status", kwargs={"public_id": self.active_order.public_id})
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Состав заказа")
        self.assertContains(response, "Борщ × 2")


class CheckoutPromoCodeTests(TestCase):
    def setUp(self):
        CafeSettings.objects.create(
            is_open=True,
            opening_time=time(0, 0),
            closing_time=time(0, 0),
            order_opening_time=time(0, 0),
            order_closing_time=time(0, 0),
            min_order_amount=Decimal("0.00"),
        )
        week = BusinessLunchWeek.objects.create(
            title="Промо-неделя",
            slug="promo-week",
            week_start=date(2026, 3, 9),
            week_end=date(2026, 3, 15),
            is_active=True,
            is_published=True,
        )
        self.lunch_day = BusinessLunchDay.objects.create(
            week=week,
            service_date=date(2026, 3, 14),
            title="Промо-ланч",
            price=Decimal("450.00"),
            is_active=True,
        )
        self.valid_promo = PromoCode.objects.create(
            code="SAVE10",
            discount_type=PromoCode.DiscountType.PERCENT,
            discount_value=10,
            valid_until=date(2026, 3, 31),
            is_active=True,
        )
        self.expired_promo = PromoCode.objects.create(
            code="OLD100",
            discount_type=PromoCode.DiscountType.FIXED,
            discount_value=100,
            valid_until=date(2026, 3, 1),
            is_active=True,
        )

    def _set_lunch_in_session(self, qty=2):
        session = self.client.session
        session[LUNCH_CART_SESSION_KEY] = {str(self.lunch_day.id): qty}
        session.save()

    def test_apply_promo_api_returns_discount(self):
        self._set_lunch_in_session()

        response = self.client.post(
            reverse("orders:api_apply_promo"),
            data={"promo_code": "save10"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertJSONEqual(
            response.content,
            {
                "ok": True,
                "promo_code": "SAVE10",
                "discount_amount": "90.00",
                "discount_label": "10%",
                "discounted_items_total": "810.00",
                "message": "Промокод применён.",
            },
        )

    @override_settings(
        YOOKASSA_SHOP_ID="test_shop",
        YOOKASSA_SECRET_KEY="test_key",
    )
    @patch("orders.views.create_yookassa_payment")
    def test_checkout_online_redirects_to_yookassa_without_creating_order(self, create_payment_mock):
        self._set_lunch_in_session()
        create_payment_mock.return_value = YooKassaPayment(
            payment_id="pay_test_123",
            status="pending",
            confirmation_url="https://yookassa.test/checkout/pay_test_123",
            raw={
                "id": "pay_test_123",
                "status": "pending",
                "confirmation": {
                    "confirmation_url": "https://yookassa.test/checkout/pay_test_123",
                },
            },
        )

        response = self.client.post(
            reverse("orders:checkout"),
            data={
                "fulfillment": Order.Fulfillment.PICKUP,
                "payment_method": Order.PaymentMethod.ONLINE,
                "customer_name": "Иван",
                "customer_phone": "+7 (900) 123-45-67",
                "promo_code": "save10",
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            response["Location"],
            "https://yookassa.test/checkout/pay_test_123",
        )
        self.assertEqual(Order.objects.count(), 0)
        self.assertEqual(OnlinePaymentAttempt.objects.count(), 1)

        attempt = OnlinePaymentAttempt.objects.get()
        self.assertEqual(attempt.payment_method, Order.PaymentMethod.ONLINE)
        self.assertEqual(attempt.promo_code, "SAVE10")
        self.assertEqual(attempt.promo_discount_amount, Decimal("90.00"))
        self.assertEqual(attempt.total, Decimal("810.00"))
        self.assertEqual(attempt.payment_id, "pay_test_123")
        self.assertIn(LUNCH_CART_SESSION_KEY, self.client.session)

    def test_checkout_rejects_expired_promo_code(self):
        self._set_lunch_in_session()

        response = self.client.post(
            reverse("orders:checkout"),
            data={
                "fulfillment": Order.Fulfillment.PICKUP,
                "payment_method": Order.PaymentMethod.UPON_RECEIPT,
                "customer_name": "Иван",
                "customer_phone": "+7 (900) 123-45-67",
                "promo_code": "old100",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Срок действия промокода истёк.")
        self.assertEqual(Order.objects.count(), 0)

    @override_settings(
        YOOKASSA_SHOP_ID="test_shop",
        YOOKASSA_SECRET_KEY="test_key",
    )
    @patch("orders.views.get_yookassa_payment")
    @patch("orders.views.create_yookassa_payment")
    def test_payment_return_creates_order_only_after_successful_payment(
        self,
        create_payment_mock,
        get_payment_mock,
    ):
        self._set_lunch_in_session()
        create_payment_mock.return_value = YooKassaPayment(
            payment_id="pay_test_456",
            status="pending",
            confirmation_url="https://yookassa.test/checkout/pay_test_456",
            raw={
                "id": "pay_test_456",
                "status": "pending",
                "confirmation": {
                    "confirmation_url": "https://yookassa.test/checkout/pay_test_456",
                },
            },
        )
        get_payment_mock.return_value = YooKassaPayment(
            payment_id="pay_test_456",
            status="succeeded",
            confirmation_url="",
            raw={
                "id": "pay_test_456",
                "status": "succeeded",
            },
        )

        checkout_response = self.client.post(
            reverse("orders:checkout"),
            data={
                "fulfillment": Order.Fulfillment.PICKUP,
                "payment_method": Order.PaymentMethod.ONLINE,
                "customer_name": "Иван",
                "customer_phone": "+7 (900) 123-45-67",
                "promo_code": "save10",
            },
        )

        self.assertEqual(checkout_response.status_code, 302)
        attempt = OnlinePaymentAttempt.objects.get()
        self.assertEqual(Order.objects.count(), 0)

        response = self.client.get(
            reverse("orders:payment_return", kwargs={"public_id": attempt.public_id})
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(Order.objects.count(), 1)

        order = Order.objects.get()
        attempt.refresh_from_db()
        self.assertEqual(attempt.status, OnlinePaymentAttempt.Status.SUCCEEDED)
        self.assertEqual(attempt.order, order)
        self.assertEqual(order.payment_method, Order.PaymentMethod.ONLINE)
        self.assertEqual(order.promo_code, "SAVE10")
        self.assertEqual(order.promo_discount_amount, Decimal("90.00"))
        self.assertEqual(order.total, Decimal("810.00"))
        self.assertNotIn(LUNCH_CART_SESSION_KEY, self.client.session)


class TelegramOrderStatusTests(TestCase):
    def setUp(self):
        self.order = Order.objects.create(
            status=Order.Status.NEW,
            fulfillment=Order.Fulfillment.PICKUP,
            payment_method=Order.PaymentMethod.UPON_RECEIPT,
            customer_name="Иван",
            customer_phone="+79001234567",
            total=Decimal("650.00"),
        )
        OrderItem.objects.create(
            order=self.order,
            product=None,
            product_name="Борщ",
            unit_price=Decimal("650.00"),
            quantity=1,
            line_total=Decimal("650.00"),
        )

    @patch("orders.telegram_handlers.sync_order_telegram_message")
    @patch("orders.telegram_handlers.answer_callback_query")
    def test_process_telegram_update_changes_order_status(
        self,
        answer_callback_query_mock,
        sync_message_mock,
    ):
        handled = process_telegram_update(
            {
                "update_id": 101,
                "callback_query": {
                    "id": "callback-1",
                    "data": f"order:{self.order.id}:status:confirmed",
                    "message": {
                        "message_id": 555,
                        "chat": {"id": -1001234567890},
                    },
                },
            }
        )

        self.assertTrue(handled)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Order.Status.CONFIRMED)
        self.assertEqual(self.order.telegram_chat_id, "-1001234567890")
        self.assertEqual(self.order.telegram_message_id, 555)
        answer_callback_query_mock.assert_called_once()
        sync_message_mock.assert_called_once_with(self.order)

    @patch.dict(os.environ, {"TELEGRAM_WEBHOOK_SECRET": "secret-123"}, clear=False)
    @patch("orders.telegram_views.process_telegram_update")
    def test_telegram_webhook_uses_shared_handler(self, process_update_mock):
        response = self.client.post(
            "/telegram/webhook/secret-123/",
            data='{"callback_query":{"id":"cb1"}}',
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        process_update_mock.assert_called_once()


class OrderAcceptanceWindowTests(TestCase):
    def setUp(self):
        CafeSettings.objects.create(
            is_open=True,
            working_hours_text="Ежедневно, 10:00–21:00",
            opening_time=time(10, 0),
            closing_time=time(21, 0),
            order_hours_text="Ежедневно, 10:00–20:00",
            order_opening_time=time(10, 0),
            order_closing_time=time(20, 0),
            min_order_amount=Decimal("0.00"),
        )
        week = BusinessLunchWeek.objects.create(
            title="Часы приёма заказов",
            slug="hours-week",
            week_start=date(2026, 3, 16),
            week_end=date(2026, 3, 22),
            is_active=True,
            is_published=True,
        )
        self.lunch_day = BusinessLunchDay.objects.create(
            week=week,
            service_date=date(2026, 3, 18),
            title="Среда",
            price=Decimal("390.00"),
            is_active=True,
        )

        session = self.client.session
        session[LUNCH_CART_SESSION_KEY] = {str(self.lunch_day.id): 1}
        session.save()

    @patch("core.models.timezone.localtime")
    def test_checkout_redirects_when_order_acceptance_is_closed(self, localtime_mock):
        localtime_mock.return_value = timezone.make_aware(
            datetime(2026, 3, 18, 20, 30),
            timezone.get_current_timezone(),
        )

        response = self.client.get(reverse("orders:checkout"), follow=True)

        self.assertRedirects(response, reverse("orders:cart"))
        self.assertContains(response, "Сейчас приём заказов недоступен.")
        self.assertContains(response, "Ежедневно, 10:00–20:00")
