from datetime import time
from django.db import models
from django.utils import timezone


class CafeSettings(models.Model):
    is_open = models.BooleanField("Принимаем заказы вручную", default=True)
    site_notice = models.CharField("Сообщение на сайте", max_length=255, blank=True)

    working_hours_text = models.CharField(
        "Текст режима работы",
        max_length=255,
        blank=True,
        default="Ежедневно, 10:00–23:00",
    )

    opening_time = models.TimeField(
        "Время открытия",
        default=time(10, 0),
    )
    closing_time = models.TimeField(
        "Время закрытия",
        default=time(22, 0),
    )

    phone = models.CharField(
        "Телефон",
        max_length=32,
        blank=True,
        default="+7 (000) 000-00-00",
    )

    address_text = models.CharField(
        "Адрес",
        max_length=255,
        blank=True,
        default="г. Ижевск, кафе «Сказка»",
    )

    min_order_amount = models.DecimalField(
        "Минимальная сумма заказа",
        max_digits=10,
        decimal_places=2,
        default=0,
    )

    delivery_fee = models.DecimalField(
        "Стоимость доставки",
        max_digits=10,
        decimal_places=2,
        default=0,
    )

    updated_at = models.DateTimeField("Обновлено", auto_now=True)

    class Meta:
        verbose_name = "Настройки кафе"
        verbose_name_plural = "Настройки кафе"

    def __str__(self):
        return "Настройки кафе"

    def is_currently_open(self, dt=None) -> bool:
        if not self.is_open:
            return False

        dt = dt or timezone.localtime()
        now_time = dt.time()

        open_time = self.opening_time
        close_time = self.closing_time

        if open_time == close_time:
            return True

        if open_time < close_time:
            return open_time <= now_time < close_time

        # режим через полночь, например 20:00–02:00
        return now_time >= open_time or now_time < close_time