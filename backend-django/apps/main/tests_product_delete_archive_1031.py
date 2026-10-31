"""31.10: удаление товара со строками приходов/возвратов/заказов поставщику архивирует товар, строки остаются."""
from decimal import Decimal
import uuid

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.main.models import Client, Product, SupplierReceiptItem
from apps.users.models import Company, SubscriptionPlan

User = get_user_model()


class ProductDeleteArchiveTests(TestCase):
    def setUp(self):
        self.api = APIClient()
        self.owner = User.objects.create_user(email=f"o_{uuid.uuid4().hex[:6]}@t.com", password="pass", role="owner")
        plan = SubscriptionPlan.objects.create(name="Pro", price=Decimal("100.00"))
        self.company = Company.objects.create(name="Co", owner=self.owner, subscription_plan=plan)
        self.owner.company = self.company
        self.owner.save()
        self.api.force_authenticate(user=self.owner)
        self.sup = Client.objects.create(full_name="Альфа", type=Client.StatusClient.SUPPLIERS, company=self.company)

    def mk(self, name):
        return Product.objects.create(name=name, company=self.company, quantity=Decimal("0"),
                                      purchase_price=Decimal("10.00"), price=Decimal("15.00"), markup_percent=Decimal("50.00"))

    def receipt(self, p):
        r = self.api.post(f"/api/main/suppliers/{self.sup.id}/receipt/", {
            "items": [{"product": str(p.id), "qty": 3, "purchase_price": "10.00"}],
            "create_deal": True, "payment_type": "debt"}, format="json")
        self.assertIn(r.status_code, (200, 201), r.data)

    def test_single_delete_with_receipt_409(self):
        p = self.mk("С приходом")
        self.receipt(p)
        r = self.api.delete(f"/api/main/products/{p.id}/")
        self.assertEqual(r.status_code, 409, r.data)
        self.assertEqual(r.data["code"], "product_has_history")
        self.assertEqual(r.data["data"]["receipts"], 1)
        p.refresh_from_db()
        self.assertNotEqual(p.status, Product.Status.ARCHIVED)  # молча не архивируем
        self.assertEqual(SupplierReceiptItem.objects.filter(product_id=p.id).count(), 1)

    def test_single_delete_without_history_deletes(self):
        p = self.mk("Без истории")
        r = self.api.delete(f"/api/main/products/{p.id}/")
        self.assertEqual(r.status_code, 204)
        self.assertFalse(Product.objects.filter(pk=p.pk).exists())

    def test_bulk_delete_mixed(self):
        a, b = self.mk("А с приходом"), self.mk("Б чистый")
        self.receipt(a)
        r = self.api.delete("/api/main/products/bulk-delete/", {"ids": [str(a.id), str(b.id)]}, format="json")
        self.assertEqual(r.status_code, 207, r.data)
        self.assertEqual(r.data["deleted"], [str(b.id)])
        self.assertEqual(r.data["protected"], [str(a.id)])
        self.assertEqual(r.data["history"][str(a.id)]["receipts"], 1)
        self.assertTrue(Product.objects.filter(pk=a.pk).exists())
        self.assertFalse(Product.objects.filter(pk=b.pk).exists())

    def test_bulk_delete_require_all_409(self):
        a, b = self.mk("А с приходом"), self.mk("Б чистый")
        self.receipt(a)
        r = self.api.delete("/api/main/products/bulk-delete/",
                            {"ids": [str(a.id), str(b.id)], "require_all": True}, format="json")
        self.assertEqual(r.status_code, 409, r.data)
        self.assertEqual(r.data["code"], "product_has_history")
        self.assertTrue(Product.objects.filter(pk=b.pk).exists())  # откат

    def test_archive_and_unarchive(self):
        p = self.mk("В архив")
        self.receipt(p)
        r = self.api.post(f"/api/main/products/{p.id}/archive/")
        self.assertEqual(r.status_code, 200, r.data)
        self.assertTrue(r.data["is_archived"])
        p.refresh_from_db()
        self.assertEqual(p.status, Product.Status.ARCHIVED)
        self.assertTrue(self.api.get(f"/api/main/products/{p.id}/?include_archived=1").data["is_archived"])
        r = self.api.post(f"/api/main/products/{p.id}/unarchive/")
        self.assertEqual(r.status_code, 200, r.data)
        self.assertFalse(r.data["is_archived"])
        p.refresh_from_db()
        self.assertIsNone(p.status)
        self.assertFalse(self.api.get(f"/api/main/products/{p.id}/?include_archived=1").data["is_archived"])
