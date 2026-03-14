from django.test import TestCase, override_settings

from catalog.models import Category, Product


class SeoInfrastructureTests(TestCase):
    @override_settings(SITE_URL="https://example.com")
    def test_robots_txt_contains_sitemap(self):
        response = self.client.get("/robots.txt")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "text/plain; charset=utf-8")
        self.assertContains(response, "User-agent: *")
        self.assertContains(response, "Disallow: /admin/")
        self.assertContains(response, "Sitemap: https://example.com/sitemap.xml")

    def test_sitemap_contains_public_catalog_urls(self):
        category = Category.objects.create(name="Супы", slug="soups", is_active=True)
        product = Product.objects.create(
            category=category,
            name="Борщ",
            slug="borsch",
            price="350.00",
            is_active=True,
        )

        response = self.client.get("/sitemap.xml")

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response["Content-Type"].startswith("application/xml"))
        self.assertContains(response, "http://testserver/")
        self.assertContains(response, f"/category/{category.slug}/")
        self.assertContains(response, f"/p/{product.slug}/")
