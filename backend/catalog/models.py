from django.db import models


class Category(models.Model):
    name = models.CharField("Название", max_length=120)
    slug = models.SlugField("Slug", max_length=140, unique=True)
    is_active = models.BooleanField("Активна", default=True)
    sort_order = models.PositiveIntegerField("Сортировка", default=100)

    class Meta:
        verbose_name = "Категория"
        verbose_name_plural = "Категории"
        ordering = ["sort_order", "name"]

    def __str__(self) -> str:
        return self.name


class Product(models.Model):
    category = models.ForeignKey(Category, on_delete=models.PROTECT, related_name="products", verbose_name="Категория")
    name = models.CharField("Название", max_length=160)
    slug = models.SlugField("Slug", max_length=180, unique=True)

    description = models.TextField("Описание", blank=True)
    price = models.DecimalField("Цена", max_digits=10, decimal_places=2)

    weight_grams = models.PositiveIntegerField("Вес (г)", null=True, blank=True)
    is_active = models.BooleanField("Активен", default=True)
    sort_order = models.PositiveIntegerField("Сортировка", default=100)

    created_at = models.DateTimeField("Создано", auto_now_add=True)
    updated_at = models.DateTimeField("Обновлено", auto_now=True)

    @property
    def main_image(self):
        main = self.images.filter(is_main=True).order_by("sort_order", "id").first()
        if main:
            return main
        return self.images.order_by("sort_order", "id").first()

    class Meta:
        verbose_name = "Блюдо"
        verbose_name_plural = "Блюда"
        ordering = ["sort_order", "name"]

    def __str__(self) -> str:
        return self.name


class ProductImage(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="images", verbose_name="Блюдо")
    image = models.ImageField("Изображение", upload_to="products/")
    alt_text = models.CharField("Alt", max_length=200, blank=True)
    is_main = models.BooleanField("Главное", default=False)
    sort_order = models.PositiveIntegerField("Сортировка", default=100)

    class Meta:
        verbose_name = "Фото блюда"
        verbose_name_plural = "Фото блюд"
        ordering = ["sort_order", "id"]

    def __str__(self) -> str:
        return f"{self.product_id} image #{self.id}"