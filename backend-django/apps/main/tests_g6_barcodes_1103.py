"""G6 (аудит 03.11): products/list/?barcodes=… — список штрихкодов одним запросом, с доп. кодами."""
from decimal import Decimal

from django.test import override_settings

from apps.main.models import Product, ProductAlternateBarcode
from apps.users.tests_tz_n16_permissions import LOCMEM, N16Base


@override_settings(CACHES=LOCMEM)
class BarcodesListTests(N16Base):
    def get(self, q):
        r = self.api_owner.get("/api/main/products/list/" + q)
        return r

    def ids(self, q):
        r = self.get(q)
        self.assertEqual(r.status_code, 200, r.content)
        return {x["id"] for x in r.json()["results"]}

    def test_barcodes(self):
        milk = Product.objects.create(company=self.company, name="Молоко", price=Decimal("80"), quantity=Decimal("3"),
                                      barcode="4870000000011")
        ProductAlternateBarcode.objects.create(company=self.company, product=milk, barcode="4870000000099")
        Product.objects.create(company=self.company, name="Кефир", price=Decimal("70"), quantity=Decimal("1"),
                               barcode="4870000000028")
        self.assertEqual(self.ids(f"?barcodes={self.product.barcode},4870000000099, 0000"),
                         {str(self.product.id), str(milk.id)})
        self.assertEqual(self.ids("?barcodes[]=4870000000011&barcodes[]=4870000000028&page_size=100"), {
            str(milk.id), *[str(p.id) for p in Product.objects.filter(barcode="4870000000028")]})
        self.assertEqual(len(self.ids("")), 3)
        too_many = ",".join(str(1000000 + i) for i in range(501))
        self.assertEqual(self.get(f"?barcodes={too_many}").status_code, 400)
