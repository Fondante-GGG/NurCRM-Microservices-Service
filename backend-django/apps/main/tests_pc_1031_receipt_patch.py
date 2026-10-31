"""ТЗ 31.10 п.21: PATCH suppliers/receipts/{id}/ — правка прихода, dry_run, версия, коды ошибок."""
from datetime import timedelta
from decimal import Decimal
import uuid

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.main.models import (
    ClientDeal, Client, DealInstallment, Product, SupplierReceipt, SupplierReceiptItem,
)
from apps.users.models import Company, CompanyAppSettings, SubscriptionPlan

User = get_user_model()


class ReceiptPatchTests(TestCase):
    def setUp(self):
        self.api = APIClient()
        self.owner = User.objects.create_user(email=f"o_{uuid.uuid4().hex[:6]}@t.com", password="pass", role="owner")
        plan = SubscriptionPlan.objects.create(name="Pro", price=Decimal("100.00"))
        self.company = Company.objects.create(name="Co", owner=self.owner, subscription_plan=plan)
        self.owner.company = self.company
        self.owner.save()
        self.api.force_authenticate(user=self.owner)
        self.sup = Client.objects.create(full_name="Альфа", type=Client.StatusClient.SUPPLIERS, company=self.company)
        self.p = Product.objects.create(name="Печенье", company=self.company, quantity=Decimal("0"),
                                        purchase_price=Decimal("10.00"), price=Decimal("15.00"))
        self.p2 = Product.objects.create(name="Чай", company=self.company, quantity=Decimal("0"),
                                         purchase_price=Decimal("5.00"), price=Decimal("8.00"))
        r = self.api.post(f"/api/main/suppliers/{self.sup.id}/receipt/", {
            "create_deal": True, "payment_type": "debt",
            "items": [{"product": str(self.p.id), "qty": 10, "purchase_price": "10.00"}]}, format="json")
        self.assertEqual(r.status_code, 200, r.data)
        self.rid = r.data["id"]
        self.deal = ClientDeal.objects.get(pk=r.data["deal_id"])
        self.item = SupplierReceiptItem.objects.get(receipt_id=self.rid)
        self.url = f"/api/main/suppliers/receipts/{self.rid}/"

    def patch(self, body, **kw):
        return self.api.patch(self.url, body, format="json", **kw)

    def employee(self, **perms):
        u = User.objects.create_user(email=f"e_{uuid.uuid4().hex[:6]}@t.com", password="pass",
                                     role="salesperson", company=self.company, **perms)
        api = APIClient()
        api.force_authenticate(user=u)
        return api

    # --- успешная правка ---
    def test_get_has_version_and_etag(self):
        r = self.api.get(self.url)
        self.assertEqual(r.data["version"], 1)
        self.assertEqual(r["ETag"], '"1"')

    def test_change_qty_and_price_recalcs_stock_and_debt(self):
        r = self.patch({"items": [{"id": str(self.item.id), "qty": 8, "purchase_price": "12.5"}],
                        "document_number": "Н-77", "comment": "исправили"}, HTTP_IF_MATCH='"1"')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data["version"], 2)
        self.assertEqual(r["ETag"], '"2"')
        self.assertEqual(r.data["total_amount"], "100.00")
        self.assertEqual(r.data["document_number"], "Н-77")
        self.assertEqual(r.data["comment"], "исправили")
        self.p.refresh_from_db()
        self.assertEqual(self.p.quantity, Decimal("8"))
        self.assertEqual(self.p.purchase_price, Decimal("12.5"))
        self.deal.refresh_from_db()
        self.assertEqual(self.deal.amount, Decimal("100.00"))
        self.assertEqual(self.deal.remaining_debt, Decimal("100.00"))

    def test_add_and_delete_lines(self):
        r = self.patch({"items": [{"product": str(self.p2.id), "qty": 4, "line_total": "21.00"}]})
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data["total_amount"], "121.00")
        self.p2.refresh_from_db()
        self.assertEqual(self.p2.quantity, Decimal("4"))
        self.assertEqual(self.p2.purchase_price, Decimal("5.25"))
        r = self.patch({"items": [{"id": str(self.item.id), "delete": True}]})
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data["total_amount"], "21.00")
        self.p.refresh_from_db()
        self.assertEqual(self.p.quantity, Decimal("0"))
        self.deal.refresh_from_db()
        self.assertEqual(self.deal.amount, Decimal("21.00"))

    def test_cannot_delete_last_line(self):
        r = self.patch({"items": [{"id": str(self.item.id), "delete": True}]})
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.data["code"], "items_empty")

    def test_dry_run_writes_nothing(self):
        r = self.api.patch(self.url + "?dry_run=1", {"items": [{"id": str(self.item.id), "qty": 5}]}, format="json")
        self.assertEqual(r.status_code, 200, r.data)
        self.assertTrue(r.data["dry_run"])
        ch = r.data["changes"]
        self.assertEqual((ch["total_before"], ch["total_after"]), ("100.00", "50.00"))
        self.assertEqual(ch["stock"][0]["quantity_after"], "5.000")
        self.assertEqual(ch["debt"]["amount_after"], "50.00")
        self.p.refresh_from_db(); self.item.refresh_from_db(); self.deal.refresh_from_db()
        self.assertEqual(self.p.quantity, Decimal("10"))
        self.assertEqual(self.item.qty, 10)
        self.assertEqual(self.deal.amount, Decimal("100.00"))
        self.assertEqual(SupplierReceipt.objects.get(pk=self.rid).version, 1)
        r = self.patch({"dry_run": True, "items": [{"id": str(self.item.id), "qty": 5}]})
        self.assertTrue(r.data["dry_run"])
        self.assertEqual(SupplierReceipt.objects.get(pk=self.rid).version, 1)

    def test_debt_with_payment_reduced_above_paid(self):
        DealInstallment.objects.filter(deal=self.deal).update(paid_amount=Decimal("30.00"))
        r = self.patch({"items": [{"id": str(self.item.id), "qty": 6}]})
        self.assertEqual(r.status_code, 200, r.data)
        self.deal.refresh_from_db()
        self.assertEqual(self.deal.amount, Decimal("60.00"))
        self.assertEqual(self.deal.remaining_debt, Decimal("30.00"))

    def test_audit_log_written(self):
        from apps.construction.models import AuditLog

        self.patch({"items": [{"id": str(self.item.id), "qty": 9}]})
        self.assertTrue(AuditLog.objects.filter(object_type="supplier_receipt", object_id=str(self.rid)).exists())

    # --- коды ошибок ---
    def test_version_conflict_if_match(self):
        r = self.patch({"comment": "x"}, HTTP_IF_MATCH='"7"')
        self.assertEqual(r.status_code, 409)
        self.assertEqual((r.data["code"], r.data["current_version"]), ("version_conflict", 1))

    def test_version_conflict_body(self):
        self.patch({"comment": "a"})
        r = self.patch({"comment": "b", "version": 1})
        self.assertEqual(r.status_code, 409)
        self.assertEqual(r.data["code"], "version_conflict")

    def test_negative_stock(self):
        Product.objects.filter(pk=self.p.pk).update(quantity=Decimal("3"))  # 7 из 10 уже продали
        r = self.patch({"items": [{"id": str(self.item.id), "qty": 2}]})
        self.assertEqual(r.status_code, 409)
        self.assertEqual(r.data["code"], "negative_stock")
        self.p.refresh_from_db()
        self.assertEqual(self.p.quantity, Decimal("3"))

    def test_debt_already_paid(self):
        DealInstallment.objects.filter(deal=self.deal).update(paid_amount=Decimal("80.00"))
        r = self.patch({"items": [{"id": str(self.item.id), "qty": 5}]})
        self.assertEqual(r.status_code, 409)
        self.assertEqual(r.data["code"], "debt_already_paid")
        self.deal.refresh_from_db()
        self.assertEqual(self.deal.amount, Decimal("100.00"))

    def test_has_returns(self):
        r = self.api.post(f"/api/main/suppliers/{self.sup.id}/returns/", {
            "receipt_id": self.rid, "reason": "defect", "compensation": "none",
            "items": [{"product_id": str(self.p.id), "qty": 1, "receipt_item_id": str(self.item.id)}]}, format="json")
        self.assertEqual(r.status_code, 201, r.data)
        r = self.patch({"items": [{"id": str(self.item.id), "qty": 9}]})
        self.assertEqual(r.status_code, 409)
        self.assertEqual(r.data["code"], "has_returns")
        self.assertEqual(self.patch({"document_number": "1"}).status_code, 200)  # шапку менять можно

    def test_period_closed(self):
        from apps.warehouse.models import WarehouseAccountingSettings

        WarehouseAccountingSettings.objects.create(company=self.company, closed_until=timezone.localdate())
        emp = self.employee(can_edit_purchase_documents=True)
        r = emp.patch(self.url, {"comment": "x"}, format="json")
        self.assertEqual(r.status_code, 409)
        self.assertEqual(r.data["code"], "period_closed")

    def test_edit_window_expired(self):
        SupplierReceipt.objects.filter(pk=self.rid).update(created_at=timezone.now() - timedelta(hours=49))
        r = self.patch({"comment": "x"})
        self.assertEqual(r.status_code, 409)
        self.assertEqual((r.data["code"], r.data["edit_window"]), ("edit_window_expired", "48h"))
        CompanyAppSettings.objects.create(company=self.company, app="nurmarket-mobile",
                                          settings={"receipt_edit_window": "always"})
        self.assertEqual(self.patch({"comment": "x"}).status_code, 200)

    def test_edit_window_24h(self):
        CompanyAppSettings.objects.create(company=self.company, app="nurmarket-mobile",
                                          settings={"receipt_edit_window": "24h"})
        SupplierReceipt.objects.filter(pk=self.rid).update(created_at=timezone.now() - timedelta(hours=25))
        self.assertEqual(self.patch({"comment": "x"}).data["code"], "edit_window_expired")

    def test_permission_denied(self):
        emp = self.employee()
        r = emp.patch(self.url, {"comment": "x"}, format="json")
        self.assertEqual(r.status_code, 403)
        self.assertEqual(r.data["code"], "permission_denied")
        emp2 = self.employee(can_edit_purchase_documents=True)
        r = emp2.patch(self.url, {"comment": "x"}, format="json")
        self.assertEqual(r.status_code, 200, r.data)

    def test_item_not_found(self):
        r = self.patch({"items": [{"id": str(uuid.uuid4()), "qty": 1}]})
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.data["code"], "item_not_found")

    def test_capability_flag(self):
        from core.capabilities import FEATURES

        self.assertIn("receipt_patch", FEATURES)
