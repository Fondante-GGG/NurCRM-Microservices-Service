"""G4 (аудит 03.11): products/list/?has_promotion=true|false."""
from decimal import Decimal

from django.test import override_settings

from apps.main.models import Product, ProductPromotionTier
from apps.users.tests_tz_n16_permissions import LOCMEM, N16Base


@override_settings(CACHES=LOCMEM)
class HasPromotionTests(N16Base):
    def ids(self, q):
        r = self.api_owner.get("/api/main/products/list/" + q)
        self.assertEqual(r.status_code, 200, r.content)
        return {x["id"] for x in r.json()["results"]}

    def test_filter(self):
        promo = Product.objects.create(company=self.company, name="Сок", price=Decimal("50"), quantity=Decimal("5"),
                                       stock=True)
        ProductPromotionTier.objects.create(product=promo, min_amount=Decimal("100"), discount_percent=Decimal("10"))
        flag_only = Product.objects.create(company=self.company, name="Чай", price=Decimal("5"), quantity=Decimal("1"),
                                           stock=True)  # галочка без ступеней — не акция
        self.assertEqual(self.ids("?has_promotion=true"), {str(promo.id)})
        no = self.ids("?has_promotion=false")
        self.assertIn(str(flag_only.id), no)
        self.assertIn(str(self.product.id), no)
        self.assertNotIn(str(promo.id), no)
        self.assertEqual(len(self.ids("")), 3)
