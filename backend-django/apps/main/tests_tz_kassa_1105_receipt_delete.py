"""ТЗ кассы 05.11 п.6–7: DELETE прихода и обязательная версия правки с кассы."""
import uuid
from decimal import Decimal

from apps.main.models import Product, SupplierReceiptVersion
from apps.main.tests_pc_1031_receipt_patch import REASON, ReceiptEditBase

KASSA = {"HTTP_X_NURMARKET_CLIENT": "kassa/1.17.70"}


class ReceiptDelete1105Tests(ReceiptEditBase):
    def delete(self, key=True, **body):
        hdr = {"HTTP_IDEMPOTENCY_KEY": str(uuid.uuid4())} if key else {}
        return self.api.delete(self.url, {"reason": REASON, **body}, format="json", **hdr)

    def test_delete_rolls_back(self):
        self.assertEqual(Product.objects.get(pk=self.p.pk).quantity, Decimal("10"))
        r = self.delete()
        self.assertEqual(r.status_code, 200, getattr(r, "data", None))
        self.assertTrue(r.data.get("deleted"))
        self.assertEqual(Product.objects.get(pk=self.p.pk).quantity, Decimal("0"))
        self.deal.refresh_from_db()
        self.assertEqual(self.deal.remaining_debt, Decimal("0.00"))
        self.assertTrue(SupplierReceiptVersion.objects.filter(receipt_id=self.rid, action="delete").exists())
        self.assertEqual(self.api.get(self.url).status_code, 404)
        ids = [x["id"] for x in (self.api.get("/api/main/suppliers/receipts/").data.get("results") or [])]
        self.assertNotIn(str(self.rid), ids)
        self.assertEqual(self.delete().status_code, 404)  # второй раз — нечего удалять

    def test_delete_sold_goods_409(self):
        Product.objects.filter(pk=self.p.pk).update(quantity=Decimal("4"))  # 6 шт. уже продано
        r = self.delete()
        self.assertEqual(r.status_code, 409, getattr(r, "data", None))
        self.assertEqual(r.data["code"], "negative_stock")

    def test_delete_needs_key_and_reason(self):
        self.assertEqual(self.delete(key=False).status_code, 400)
        r = self.api.delete(self.url, {}, format="json", HTTP_IDEMPOTENCY_KEY=str(uuid.uuid4()))
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.data["code"], "reason_required")

    def test_kassa_patch_without_version_428(self):
        body = {"reason": REASON, "lines": [{"id": str(self.item.id), "qty": "9"}]}
        r = self.api.patch(self.url, body, format="json", HTTP_IDEMPOTENCY_KEY=str(uuid.uuid4()), **KASSA)
        self.assertEqual(r.status_code, 428, getattr(r, "data", None))
        self.assertEqual(r.data["code"], "version_required")
        r = self.api.patch(self.url, {**body, "version": 1}, format="json",
                           HTTP_IDEMPOTENCY_KEY=str(uuid.uuid4()), **KASSA)
        self.assertEqual(r.status_code, 200, getattr(r, "data", None))
