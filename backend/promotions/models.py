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