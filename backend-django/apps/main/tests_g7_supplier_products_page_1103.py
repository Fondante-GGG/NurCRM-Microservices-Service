"""G7 (аудит 03.11): suppliers/{id}/products/?page_size=."""
from decimal import Decimal

from django.test import override_settings

from apps.main.models import Client, Product
from apps.users.tests_tz_n16_permissions import LOCMEM, N16Base


@override_settings(CACHES=LOCMEM)
class SupplierProductsPageTests(N16Base):
    def test_page_size(self):
        sup = Client.objects.create(company=self.company, full_name="Пост", phone="+996555000444",
                                    type=Client.StatusClient.SUPPLIERS)
        for i in range(5):
            p = Product.objects.create(company=self.company, name=f"Т{i}", price=Decimal("1"), quantity=Decimal("1"))
            p.suppliers.add(sup)
        url = f"/api/main/suppliers/{sup.id}/products/"
        r = self.api_owner.get(url + "?page_size=2")
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual((r.json()["count"], len(r.json()["results"])), (5, 2))
        self.assertIsNotNone(r.json()["next"])
        r = self.api_owner.get(url)
        self.assertEqual(len(r.json()["results"]), 5)
