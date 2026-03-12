from decimal import Decimal
from django.db import models
from django.utils import timezone
from datetime import time


class CafeSettings(models.Model):
    is_open = models.BooleanField("Принимаем заказы вручную", default=True)
    site_notice = models.CharField("Сообщение на сайте", max_length=255, blank=True)

    working_hours_text = models.CharField(
        "Текст режима работы",
        max_length=255,
        blank=True,
        default="Ежедневно, 10:00–22:00",
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
        "Стоимость доставки по умолчанию",
        max_digits=10,
        decimal_places=2,
        default=0,
    )

    yandex_maps_api_key = models.CharField(
        "Yandex Maps API key",
        max_length=255,
        blank=True,
    )

    yandex_suggest_api_key = models.CharField(
        "Yandex Suggest API key",
        max_length=255,
        blank=True,
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

        return now_time >= open_time or now_time < close_time


class DeliveryZone(models.Model):
    name = models.CharField("Название зоны", max_length=120)
    code = models.SlugField("Код зоны", max_length=64, unique=True)

    is_active = models.BooleanField("Активна", default=True)
    sort_order = models.PositiveIntegerField("Сортировка", default=100)

    delivery_fee = models.DecimalField(
        "Стоимость доставки",
        max_digits=10,
        decimal_places=2,
        default=Decimal("0.00"),
    )

    min_order_amount = models.DecimalField(
        "Минимальная сумма заказа для зоны",
        max_digits=10,
        decimal_places=2,
        default=Decimal("0.00"),
    )

    polygon_json = models.TextField(
        "Полигон JSON",
        help_text='JSON-массив точек вида [[lon, lat], [lon, lat], ...]. Минимум 3 точки.',
    )

    created_at = models.DateTimeField("Создано", auto_now_add=True)
    updated_at = models.DateTimeField("Обновлено", auto_now=True)

    class Meta:
        verbose_name = "Зона доставки"
        verbose_name_plural = "Зоны доставки"
        ordering = ["sort_order", "name"]

    def __str__(self):
        return self.name
    

class BusinessLunchMenu(models.Model):
    title = models.CharField("Заголовок", max_length=160)
    slug = models.SlugField("Slug", max_length=180, unique=True)

    description = models.TextField("Описание", blank=True)

    week_start = models.DateField("Начало недели")
    week_end = models.DateField("Конец недели")

    is_active = models.BooleanField("Активно", default=True)
    is_published = models.BooleanField("Опубликовано", default=True)

    sort_order = models.PositiveIntegerField("Сортировка", default=100)

    created_at = models.DateTimeField("Создано", auto_now_add=True)
    updated_at = models.DateTimeField("Обновлено", auto_now=True)

    class Meta:
        verbose_name = "Меню бизнес-ланчей"
        verbose_name_plural = "Меню бизнес-ланчей"
        ordering = ["-week_start", "sort_order", "-id"]

    def __str__(self):
        return f"{self.title} ({self.week_start} — {self.week_end})"

    @property
    def is_current(self):
        today = timezone.localdate()
        return self.is_active and self.is_published and self.week_start <= today <= self.week_end


class BusinessLunchItem(models.Model):
    menu = models.ForeignKey(
        BusinessLunchMenu,
        on_delete=models.CASCADE,
        related_name="items",
        verbose_name="Меню",
    )

    name = models.CharField("Название", max_length=160)
    description = models.TextField("Описание", blank=True)

    price = models.DecimalField("Цена", max_digits=10, decimal_places=2)

    image = models.ImageField("Изображение", upload_to="business_lunches/", blank=True)
    sort_order = models.PositiveIntegerField("Сортировка", default=100)

    class Meta:
        verbose_name = "Позиция бизнес-ланча"
        verbose_name_plural = "Позиции бизнес-ланча"
        ordering = ["sort_order", "id"]

    def __str__(self):
        return self.name
    

class ServicePage(models.Model):
    class PageType(models.TextChoices):
        BANQUETS = "banquets", "Банкеты"
        CATERING = "catering", "Кейтеринг"

    page_type = models.CharField(
        "Тип страницы",
        max_length=32,
        choices=PageType.choices,
        unique=True,
    )

    title = models.CharField("Заголовок", max_length=160)
    subtitle = models.TextField("Подзаголовок", blank=True)

    content = models.TextField("Основной текст", blank=True)
    features = models.TextField(
        "Преимущества / условия",
        blank=True,
        help_text="По одному пункту с новой строки.",
    )

    cta_title = models.CharField("Заголовок CTA", max_length=160, blank=True)
    cta_text = models.TextField("Текст CTA", blank=True)

    is_published = models.BooleanField("Опубликовано", default=True)
    updated_at = models.DateTimeField("Обновлено", auto_now=True)

    class Meta:
        verbose_name = "Страница услуги"
        verbose_name_plural = "Страницы услуг"
        ordering = ["page_type"]

    def __str__(self):
        return self.get_page_type_display()