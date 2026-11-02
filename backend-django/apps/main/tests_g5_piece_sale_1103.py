"""G5 (аудит 03.11): products/list/?piece_sale=true|false."""
from decimal import Decimal

from django.test import override_settings

from apps.main.models import Product, ProductPackage
from apps.users.tests_tz_n16_permissions import LOCMEM, N16Base


@override_settings(CACHES=LOCMEM)
class PieceSaleTests(N16Base):
    def ids(self, q):
        r = self.api_owner.get("/api/main/products/list/" + q)
        self.assertEqual(r.status_code, 200, r.content)
        return {x["id"] for x in r.json()["results"]}

    def test_filter(self):
        cig = Product.objects.create(company=self.company, name="Сигареты", price=Decimal("200"), quantity=Decimal("10"))
        ProductPackage.objects.create(company=self.company, product=cig, name="Пачка", quantity_in_package=Decimal("20"),
                                      piece_unit_price=Decimal("12"))
        kit = Product.objects.create(company=self.company, name="Набор", price=Decimal("300"), quantity=Decimal("1"),
                                     kind=Product.Kind.BUNDLE)
        ProductPackage.objects.create(company=self.company, product=kit, name="Хлеб", quantity_in_package=Decimal("2"))
        self.assertEqual(self.ids("?piece_sale=true"), {str(cig.id)})
        self.assertEqual(self.ids("?piece_sale=false"), {str(kit.id), str(self.product.id)})
