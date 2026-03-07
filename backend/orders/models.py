from django.db import models
from catalog.models import Product
import uuid


class Order(models.Model):
    class Status(models.TextChoices):
        NEW = "new", "Новый"
        CONFIRMED = "confirmed", "Подтверждён"
        COOKING = "cooking", "Готовится"
        ON_THE_WAY = "on_the_way", "В пути"
        DONE = "done", "Выполнен"
        CANCELED = "canceled", "Отменён"

    class Fulfillment(models.TextChoices):
        DELIVERY = "delivery", "Доставка"
        PICKUP = "pickup", "Самовывоз"

    status = models.CharField("Статус", max_length=20, choices=Status.choices, default=Status.NEW)
    fulfillment = models.CharField("Способ получения", max_length=20, choices=Fulfillment.choices, default=Fulfillment.DELIVERY)

    customer_name = models.CharField("Имя", max_length=120)
    customer_phone = models.CharField("Телефон", max_length=32)

    customer_comment = models.TextField("Комментарий клиента", blank=True)

    # Адрес (в MVP без карты зон; просто текст)
    address_line = models.CharField("Адрес строкой", max_length=255, blank=True)
    address_entrance = models.CharField("Подъезд", max_length=20, blank=True)
    address_floor = models.CharField("Этаж", max_length=20, blank=True)
    address_apartment = models.CharField("Квартира/офис", max_length=20, blank=True)

    total = models.DecimalField("Итого", max_digits=10, decimal_places=2, default=0)

    created_at = models.DateTimeField("Создано", auto_now_add=True)
    updated_at = models.DateTimeField("Обновлено", auto_now=True)

    # public_id = models.UUIDField("Публичный идентификатор", default=uuid.uuid4, unique=True, editable=False) to be deleted
    # public_id = models.UUIDField("Публичный идентификатор", default=uuid.uuid4, null=True, editable=False) to be deleted
    public_id = models.UUIDField("Публичный идентификатор", default=uuid.uuid4, unique=True, editable=False)

    class Meta:
        verbose_name = "Заказ"
        verbose_name_plural = "Заказы"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"Order #{self.id}"

    def recalc_total(self) -> None:
        total = 0
        for item in self.items.all():
            total += float(item.line_total)
        self.total = total
        self.save(update_fields=["total"])


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items", verbose_name="Заказ")
    product = models.ForeignKey(Product, on_delete=models.PROTECT, verbose_name="Блюдо")

    product_name = models.CharField("Название на момент заказа", max_length=160)
    unit_price = models.DecimalField("Цена за единицу", max_digits=10, decimal_places=2)
    quantity = models.PositiveIntegerField("Количество", default=1)
    line_total = models.DecimalField("Сумма", max_digits=10, decimal_places=2)

    class Meta:
        verbose_name = "Позиция заказа"
        verbose_name_plural = "Позиции заказа"

    def __str__(self) -> str:
        return f"{self.product_name} x{self.quantity}"

    def save(self, *args, **kwargs):
        self.line_total = self.unit_price * self.quantity
        super().save(*args, **kwargs)