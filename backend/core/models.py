from decimal import Decimal
from django.db import models
from django.utils import timezone
from datetime import time

from catalog.models import Product


class CafeSettings(models.Model):
    is_open = models.BooleanField("Принимаем заказы вручную", default=True)
    site_notice = models.CharField("Сообщение на сайте", max_length=255, blank=True)

    working_hours_text = models.CharField(
        "Текст режима работы",
        max_length=255,
        blank=True,
        default="Ежедневно, 10:00–21:00",
    )

    opening_time = models.TimeField(
        "Время открытия",
        default=time(10, 0),
    )
    closing_time = models.TimeField(
        "Время закрытия",
        default=time(21, 0),
    )

    order_hours_text = models.CharField(
        "Текст приема заказов",
        max_length=255,
        blank=True,
        default="Ежедневно, 10:00–20:00",
    )

    order_opening_time = models.TimeField(
        "Начало приема заказов",
        default=time(10, 0),
    )
    order_closing_time = models.TimeField(
        "Окончание приема заказов",
        default=time(20, 0),
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

    def _is_within_time_range(self, start_time, end_time, dt=None) -> bool:
        dt = dt or timezone.localtime()
        now_time = dt.time()
        if start_time == end_time:
            return True

        if start_time < end_time:
            return start_time <= now_time < end_time

        return now_time >= start_time or now_time < end_time

    @property
    def order_hours_display(self) -> str:
        return self.order_hours_text or self.working_hours_text

    def is_currently_open(self, dt=None) -> bool:
        if not self.is_open:
            return False
        return self._is_within_time_range(self.opening_time, self.closing_time, dt=dt)

    def is_accepting_orders_now(self, dt=None) -> bool:
        if not self.is_currently_open(dt=dt):
            return False
        return self._is_within_time_range(
            self.order_opening_time,
            self.order_closing_time,
            dt=dt,
        )


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
    

# class BusinessLunchMenu(models.Model):
#     title = models.CharField("Заголовок", max_length=160)
#     slug = models.SlugField("Slug", max_length=180, unique=True)

#     description = models.TextField("Описание", blank=True)

#     week_start = models.DateField("Начало недели")
#     week_end = models.DateField("Конец недели")

#     is_active = models.BooleanField("Активно", default=True)
#     is_published = models.BooleanField("Опубликовано", default=True)

#     sort_order = models.PositiveIntegerField("Сортировка", default=100)

#     created_at = models.DateTimeField("Создано", auto_now_add=True)
#     updated_at = models.DateTimeField("Обновлено", auto_now=True)

#     class Meta:
#         verbose_name = "Меню бизнес-ланчей"
#         verbose_name_plural = "Меню бизнес-ланчей"
#         ordering = ["-week_start", "sort_order", "-id"]

#     def __str__(self):
#         return f"{self.title} ({self.week_start} — {self.week_end})"

#     @property
#     def is_current(self):
#         today = timezone.localdate()
#         return self.is_active and self.is_published and self.week_start <= today <= self.week_end


# class BusinessLunchItem(models.Model):
#     menu = models.ForeignKey(
#         BusinessLunchMenu,
#         on_delete=models.CASCADE,
#         related_name="items",
#         verbose_name="Меню",
#     )

#     name = models.CharField("Название", max_length=160)
#     description = models.TextField("Описание", blank=True)

#     price = models.DecimalField("Цена", max_digits=10, decimal_places=2)

#     image = models.ImageField("Изображение", upload_to="business_lunches/", blank=True)
#     sort_order = models.PositiveIntegerField("Сортировка", default=100)

#     class Meta:
#         verbose_name = "Позиция бизнес-ланча"
#         verbose_name_plural = "Позиции бизнес-ланча"
#         ordering = ["sort_order", "id"]

#     def __str__(self):
#         return self.name


class BusinessLunchWeek(models.Model):
    title = models.CharField("Заголовок недели", max_length=160)
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
        verbose_name = "Неделя бизнес-ланчей"
        verbose_name_plural = "Недели бизнес-ланчей"
        ordering = ["-week_start", "sort_order", "-id"]

    def __str__(self):
        return f"{self.title} ({self.week_start} — {self.week_end})"


class BusinessLunchDay(models.Model):
    week = models.ForeignKey(
        BusinessLunchWeek,
        on_delete=models.CASCADE,
        related_name="days",
        verbose_name="Неделя",
    )

    service_date = models.DateField("Дата")
    title = models.CharField("Название дня", max_length=160)
    description = models.TextField("Описание", blank=True)

    price = models.DecimalField("Цена бизнес-ланча", max_digits=10, decimal_places=2)

    is_active = models.BooleanField("Активно", default=True)
    sort_order = models.PositiveIntegerField("Сортировка", default=100)

    created_at = models.DateTimeField("Создано", auto_now_add=True)
    updated_at = models.DateTimeField("Обновлено", auto_now=True)

    class Meta:
        verbose_name = "День бизнес-ланча"
        verbose_name_plural = "Дни бизнес-ланчей"
        ordering = ["service_date", "sort_order", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["week", "service_date"],
                name="unique_business_lunch_day_per_week_date",
            )
        ]

    def __str__(self):
        return f"{self.title} ({self.service_date})"

    @property
    def display_name(self):
        return f"Бизнес-ланч · {self.title}"


class BusinessLunchDayItem(models.Model):
    day = models.ForeignKey(
        BusinessLunchDay,
        on_delete=models.CASCADE,
        related_name="items",
        verbose_name="День",
    )

    role = models.CharField(
        "Роль / категория",
        max_length=80,
        blank=True,
        help_text='Например: "Салат", "Суп", "Горячее", "Напиток".',
    )

    product = models.ForeignKey(
        Product,
        on_delete=models.PROTECT,
        related_name="business_lunch_day_items",
        verbose_name="Товар из меню",
    )

    sort_order = models.PositiveIntegerField("Сортировка", default=100)

    class Meta:
        verbose_name = "Позиция дня бизнес-ланча"
        verbose_name_plural = "Позиции дней бизнес-ланчей"
        ordering = ["sort_order", "id"]

    def __str__(self):
        if self.role:
            return f"{self.role}: {self.product.name}"
        return self.product.name
    

class ServicePage(models.Model):
    class PageType(models.TextChoices):
        BANQUETS = "banquets", "Банкеты"
        CATERING = "catering", "Кейтеринг"
        CHILDREN_PARTIES = "children_parties", "Детские праздники"

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
