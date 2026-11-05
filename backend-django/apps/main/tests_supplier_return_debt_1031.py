"""31.10: возврат поставщику «списанием долга» уменьшает долг нужного прихода, излишек — старые долги по очереди."""
from decimal import Decimal
import uuid

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.main.models import Client, ClientDeal, Product, SupplierReceiptItem
from apps.users.models import Company, SubscriptionPlan

User = get_user_model()


class SupplierReturnDebtOffsetTests(TestCase):
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
                                        purchase_price=Decimal("10.00"), price=Decimal("15.00"), markup_percent=Decimal("50.00"))

    def receipt(self, qty):
        r = self.api.post(f"/api/main/suppliers/{self.sup.id}/receipt/", {
            "items": [{"product": str(self.p.id), "qty": qty, "purchase_price": "10.00"}],
            "create_deal": True, "payment_type": "debt"}, format="json")
        self.assertIn(r.status_code, (200, 201), r.data)
        rid = r.data.get("receipt_id") or r.data.get("id")
        return rid, ClientDeal.objects.get(pk=r.data["deal_id"])

    def ret(self, rid, qty):
        item = SupplierReceiptItem.objects.get(receipt_id=rid)
        r = self.api.post(f"/api/main/suppliers/{self.sup.id}/returns/", {
            "receipt_id": rid, "reason": "defect", "compensation": "debt_offset",
            "items": [{"product_id": str(self.p.id), "qty": qty, "receipt_item_id": str(item.id)}]}, format="json")
        self.assertEqual(r.status_code, 201, r.data)

    def test_offset_goes_to_return_receipt_not_latest(self):
        rid1, d1 = self.receipt(10)  # долг 100
        rid2, d2 = self.receipt(5)   # долг 50 (последняя сделка)
        self.ret(rid1, 3)            # возврат 30 по первому приходу
        d1.refresh_from_db(); d2.refresh_from_db()
        self.assertEqual(d1.remaining_debt, Decimal("70.00"))
        self.assertEqual(d2.remaining_debt, Decimal("50.00"))

    def test_excess_goes_to_older_open_debts(self):
        rid1, d1 = self.receipt(2)   # долг 20
        rid2, d2 = self.receipt(10)  # долг 100
        d1.prepayment = d1.amount    # первый уже погашен
        d1.save(update_fields=["prepayment"])
        self.ret(rid1, 2)            # возврат 20 по погашенному приходу → уходит на открытый долг
        d2.refresh_from_db()
        self.assertEqual(d2.remaining_debt, Decimal("80.00"))

    def test_return_same_key_no_second_return(self):
        # ТЗ 31.10 п.1: повтор возврата поставщику с тем же ключом не создаёт второй возврат
        from apps.main.models import SupplierReturn
        rid, _ = self.receipt(10)
        item = SupplierReceiptItem.objects.get(receipt_id=rid)
        body = {"receipt_id": rid, "reason": "defect", "compensation": "none",
                "items": [{"product_id": str(self.p.id), "qty": 1, "receipt_item_id": str(item.id)}]}
        url = f"/api/main/suppliers/{self.sup.id}/returns/"
        r1 = self.api.post(url, body, format="json", HTTP_IDEMPOTENCY_KEY="ret-1")
        r2 = self.api.post(url, body, format="json", HTTP_IDEMPOTENCY_KEY="ret-1")
        self.assertEqual(r1.status_code, 201, r1.data)
        self.assertEqual(r2.status_code, 201)
        self.assertTrue(r2.data.get("replayed"))
        self.assertEqual(SupplierReturn.objects.filter(company=self.company).count(), 1)


class SupplierReturnDebtOffset1105Tests(SupplierReturnDebtOffsetTests):
    """ТЗ кассы 05.11 п.1: зачёт не создаёт переплату и не уходит на чужой долг."""

    def payables_row(self):
        r = self.api.get("/api/main/suppliers/payables/")
        self.assertEqual(r.status_code, 200, r.data)
        rows = [x for x in r.data["items"] if x["supplier_id"] == str(self.sup.id)]
        return rows[0] if rows else None

    def test_offset_no_overpayment(self):
        rid, d = self.receipt(10)  # долг 100
        self.ret(rid, 3)
        d.refresh_from_db()
        self.assertEqual(d.remaining_debt, Decimal("70.00"))
        self.assertEqual(d.prepayment, Decimal("0.00"))
        row = self.payables_row()
        self.assertEqual(Decimal(row["debt"]), Decimal("70.00"))
        self.assertEqual(Decimal(row["prepayment_total"]), Decimal("0.00"))
        from apps.main.models import SupplierReceipt
        from apps.main.views import _receipt_payment_info
        info = _receipt_payment_info([SupplierReceipt.objects.get(pk=rid)])[str(rid)]
        self.assertEqual(Decimal(info["debt_amount"]), Decimal("70.00"))

    def test_receipt_without_deal_offsets_itself(self):
        rid_old, d_old = self.receipt(10)  # старый долг со сделкой 100
        r = self.api.post(f"/api/main/suppliers/{self.sup.id}/receipt/", {
            "items": [{"product": str(self.p.id), "qty": 1, "purchase_price": "10.00"}],
            "payment_type": "debt"}, format="json")  # без create_deal — сделки нет
        self.assertIn(r.status_code, (200, 201), r.data)
        rid = r.data.get("receipt_id") or r.data.get("id")
        self.ret(rid, 1)
        d_old.refresh_from_db()
        self.assertEqual(d_old.remaining_debt, Decimal("100.00"))
        self.assertEqual(d_old.prepayment, Decimal("0.00"))
        from apps.main.models import SupplierReceipt
        from apps.main.views import _receipt_payment_info
        info = _receipt_payment_info([SupplierReceipt.objects.get(pk=rid)])[str(rid)]
        self.assertEqual(info["payment_type"], "debt")
        self.assertEqual(Decimal(info["debt_amount"]), Decimal("0.00"))


class SupplierReturnKassaDeal1105Tests(SupplierReturnDebtOffsetTests):
    """05.11: сделка, созданная кассой (метка «receipt:<id> · …» без скобок), тоже уменьшается."""

    def test_kassa_style_deal(self):
        from datetime import date
        r = self.api.post(f"/api/main/suppliers/{self.sup.id}/receipt/", {
            "items": [{"product": str(self.p.id), "qty": 10, "purchase_price": "10.00"}],
            "payment_type": "debt"}, format="json")
        rid = r.data.get("receipt_id") or r.data.get("id")
        d = ClientDeal.objects.create(company=self.company, client=self.sup, kind=ClientDeal.Kind.DEBT,
                                      title="Долг", amount=Decimal("100.00"), debt_months=1, first_due_date=date.today(),
                                      note=f"receipt:{rid} · приход 05.11.2026 16:48, срок 30 дн. · NurCRM")
        self.ret(rid, 3)
        d.refresh_from_db()
        self.assertEqual(d.remaining_debt, Decimal("70.00"))
        self.assertEqual(d.prepayment, Decimal("0.00"))


class FixSupplierDebtOffsetCommandTests(SupplierReturnDebtOffsetTests):
    def test_command_repairs_old_corruption(self):
        from io import StringIO
        from django.core.management import call_command
        from apps.main.models import SupplierReturn, SupplierReturnItem
        rid_old, d_old = self.receipt(10)   # чужой долг 100
        rid, d = self.receipt(5)            # свой долг 50
        item = SupplierReceiptItem.objects.get(receipt_id=rid)
        r = SupplierReturn.objects.create(company=self.company, supplier=self.sup, receipt_id=rid,
                                          compensation="debt_offset", number=1)
        SupplierReturnItem.objects.create(supplier_return=r, product=self.p, receipt_item=item, qty=2,
                                          purchase_price=Decimal("10.00"))
        # старый код: 20 ушло в prepayment чужой сделки
        d_old.prepayment = Decimal("20.00"); d_old.save()
        call_command("fix_supplier_debt_offset", stdout=StringIO())  # dry-run
        d_old.refresh_from_db(); self.assertEqual(d_old.prepayment, Decimal("20.00"))
        call_command("fix_supplier_debt_offset", "--apply", stdout=StringIO())
        d_old.refresh_from_db(); d.refresh_from_db()
        self.assertEqual(d_old.prepayment, Decimal("0.00"))
        self.assertEqual(d_old.remaining_debt, Decimal("100.00"))
        self.assertEqual(d.remaining_debt, Decimal("30.00"))
        self.assertEqual(d.prepayment, Decimal("0.00"))
