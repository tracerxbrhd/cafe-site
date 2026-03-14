from django.core.exceptions import ValidationError
from django.db import models


class PromoBanner(models.Model):
    title = models.CharField("Заголовок", max_length=160)
    subtitle = models.TextField("Подзаголовок", blank=True)

    image = models.ImageField("Изображение", upload_to="promo_banners/")
    button_text = models.CharField("Текст кнопки", max_length=60, blank=True)
    button_url = models.CharField("Ссылка кнопки", max_length=255, blank=True)

    is_active = models.BooleanField("Активен", default=True)
    sort_order = models.PositiveIntegerField("Сортировка", default=100)

    created_at = models.DateTimeField("Создано", auto_now_add=True)
    updated_at = models.DateTimeField("Обновлено", auto_now=True)

    class Meta:
        verbose_name = "Промо-баннер"
        verbose_name_plural = "Промо-баннеры"
        ordering = ["sort_order", "-created_at", "id"]

    def __str__(self) -> str:
        return self.title


class PromoCode(models.Model):
    class DiscountType(models.TextChoices):
        FIXED = "fixed", "Сумма в рублях"
        PERCENT = "percent", "Проценты"

    code = models.CharField("Промокод", max_length=32, unique=True)
    discount_type = models.CharField(
        "Тип скидки",
        max_length=16,
        choices=DiscountType.choices,
        default=DiscountType.FIXED,
    )
    discount_value = models.PositiveIntegerField("Размер скидки")
    valid_until = models.DateField("Действует до", null=True, blank=True)
    is_active = models.BooleanField("Активен", default=True)
    created_at = models.DateTimeField("Создано", auto_now_add=True)
    updated_at = models.DateTimeField("Обновлено", auto_now=True)

    class Meta:
        verbose_name = "Промокод"
        verbose_name_plural = "Промокоды"
        ordering = ["code"]

    def __str__(self) -> str:
        return self.code

    def clean(self):
        self.code = (self.code or "").strip().upper()

        if not self.code:
            raise ValidationError({"code": "Укажите код промокода."})

        if self.discount_type == self.DiscountType.PERCENT:
            if self.discount_value < 1 or self.discount_value > 100:
                raise ValidationError(
                    {"discount_value": "Процент скидки должен быть от 1 до 100."}
                )
        elif self.discount_value < 1:
            raise ValidationError(
                {"discount_value": "Сумма скидки должна быть больше нуля."}
            )

    def save(self, *args, **kwargs):
        self.code = (self.code or "").strip().upper()
        super().save(*args, **kwargs)

    @property
    def discount_label(self) -> str:
        if self.discount_type == self.DiscountType.PERCENT:
            return f"{self.discount_value}%"
        return f"{self.discount_value} ₽"
