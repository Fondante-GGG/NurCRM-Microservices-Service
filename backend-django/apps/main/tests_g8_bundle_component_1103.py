"""G8 (аудит 03.11): состав комплекта — packages_input[].product_id, старые строки по названию работают."""
import uuid
from decimal import Decimal

from django.test import override_settings

from apps.main.models import Product, ProductPackage
from apps.users.models import Company, User
from apps.users.tests_tz_n16_permissions import LOCMEM, N16Base


@override_settings(CACHES=LOCMEM)
class BundleComponentTests(N16Base):
    def setUp(self):
        super().setUp()
        self.kit = Product.objects.create(company=self.company, name="Набор", price=Decimal("300"),
                                          quantity=Decimal("1"), kind=Product.Kind.BUNDLE)
        self.url = f"/api/main/products/{self.kit.id}/"

    def patch(self, rows):
        return self.api_owner.patch(self.url, {"packages_input": rows}, format="json")

    def test_product_id_saved_and_returned(self):
        r = self.patch([{"name": "Хлеб", "quantity_in_package": "2", "unit": "шт", "piece_unit_price": "0",
                         "product_id": str(self.product.id)}])
        self.assertEqual(r.status_code, 200, r.content)
        pk = ProductPackage.objects.get(product=self.kit)
        self.assertEqual(pk.component_id, self.product.id)
        got = self.api_owner.get(self.url).json()["packages"][0]
        self.assertEqual((got["product_id"], got["product_name"], got["name"]), (str(self.product.id), "Хлеб", "Хлеб"))

    def test_old_rows_by_name_still_work(self):
        r = self.patch([{"name": "Хлеб", "quantity_in_package": "2", "unit": "шт", "piece_unit_price": "0"}])
        self.assertEqual(r.status_code, 200, r.content)
        pk = ProductPackage.objects.get(product=self.kit)
        self.assertIsNone(pk.component_id)
        got = self.api_owner.get(self.url).json()["packages"][0]
        self.assertIsNone(got["product_id"])
        self.assertEqual(got["name"], "Хлеб")

    def test_foreign_or_self_component_rejected(self):
        other_owner = User.objects.create_user(email=f"x{uuid.uuid4().hex[:6]}@t.kg", password="x")
        alien = Product.objects.create(company=Company.objects.create(name="X", owner=other_owner), name="Чужой",
                                       price=Decimal("1"), quantity=Decimal("1"))
        for pid in (alien.id, self.kit.id):
            r = self.patch([{"name": "Х", "quantity_in_package": "1", "piece_unit_price": "0", "product_id": str(pid)}])
            self.assertEqual(r.status_code, 400, r.content)
        self.assertFalse(ProductPackage.objects.filter(product=self.kit).exists())

    def test_component_deleted_keeps_row(self):
        self.patch([{"name": "Хлеб", "quantity_in_package": "1", "piece_unit_price": "0",
                     "product_id": str(self.product.id)}])
        ProductPackage.objects.filter(product=self.kit).update(component_id=uuid.uuid4())  # ссылка «в никуда»
        r = self.api_owner.get(self.url)
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(r.json()["packages"][0]["name"], "Хлеб")
