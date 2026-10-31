"""ТЗ 31.10 п.20: номер прихода «ПР-…», номер возврата «ВП-…», цены продажи в строке прихода."""
from decimal import Decimal
import uuid

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.main.models import Client, Product, SupplierReceiptItem, SupplierReturn
from apps.users.models import Company, SubscriptionPlan

User = get_user_model()


class ReceiptNumberingTests(TestCase):
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
                                        purchase_price=Decimal("10.00"), price=Decimal("15.00"),
                                        markup_percent=Decimal("50.00"))
        self.year = timezone.localdate().year

    def receipt(self, **line):
        r = self.api.post(f"/api/main/suppliers/{self.sup.id}/receipt/", {
            "items": [{"product": str(self.p.id), "qty": 10, "purchase_price": "10.00", **line}]}, format="json")
        self.assertEqual(r.status_code, 200, r.data)
        return r

    def ret(self, rid):
        item = SupplierReceiptItem.objects.get(receipt_id=rid)
        r = self.api.post(f"/api/main/suppliers/{self.sup.id}/returns/", {
            "receipt_id": rid, "reason": "defect", "compensation": "none",
            "items": [{"product_id": str(self.p.id), "qty": 1, "receipt_item_id": str(item.id)}]}, format="json")
        self.assertEqual(r.status_code, 201, r.data)
        return r

    def test_receipt_number_display(self):
        r1 = self.receipt()
        r2 = self.receipt()
        self.assertEqual(r2.data["number"], 2)
        self.assertEqual(r2.data["number_display"], f"ПР-{self.year}-000002")
        self.assertEqual((r2.data["series"], r2.data["year"], r2.data["sequence"]), ("ПР", self.year, 2))
        g = self.api.get(f"/api/main/suppliers/receipts/{r1.data['id']}/")
        self.assertEqual(g.data["number"], 1)
        self.assertEqual(g.data["number_display"], f"ПР-{self.year}-000001")
        lst = self.api.get("/api/main/suppliers/receipts/", {"number": f"ПР-{self.year}-000002"})
        self.assertEqual([x["id"] for x in lst.data["results"]], [r2.data["id"]])

    def test_return_number_and_filter(self):
        rid = self.receipt().data["id"]
        a = self.ret(rid)
        b = self.ret(rid)
        self.assertEqual((a.data["number"], b.data["number"]), (1, 2))
        self.assertEqual(b.data["number_display"], f"ВП-{self.year}-000002")
        self.assertEqual(b.data["series"], "ВП")
        lst = self.api.get("/api/main/suppliers/returns/", {"number": f"ВП-{self.year}-000001"})
        self.assertEqual([x["id"] for x in lst.data["results"]], [a.data["id"]])
        lst = self.api.get("/api/main/suppliers/returns/", {"number": "2"})
        self.assertEqual([x["id"] for x in lst.data["results"]], [b.data["id"]])

    def test_return_numbers_per_company(self):
        other_owner = User.objects.create_user(email=f"x_{uuid.uuid4().hex[:6]}@t.com", password="pass", role="owner")
        other = Company.objects.create(name="Other", owner=other_owner, subscription_plan=SubscriptionPlan.objects.first())
        sup2 = Client.objects.create(full_name="Б", type=Client.StatusClient.SUPPLIERS, company=other)
        SupplierReturn.objects.create(company=other, supplier=sup2, reason="defect", compensation="none")
        rid = self.receipt().data["id"]
        self.assertEqual(self.ret(rid).data["number"], 1)

    def test_line_prices_snapshot(self):
        r = self.receipt(price="18.00")
        g = self.api.get(f"/api/main/suppliers/receipts/{r.data['id']}/")
        line = g.data["items"][0]
        self.assertEqual(line["previous_sale_price"], "15.00")
        self.assertEqual(line["sale_price"], "18.00")
        self.assertEqual(Decimal(line["markup_percent"]), Decimal("80.00"))

    def test_line_prices_without_price_change(self):
        r = self.receipt(purchase_price="12.00")
        line = self.api.get(f"/api/main/suppliers/receipts/{r.data['id']}/").data["items"][0]
        self.assertEqual(line["previous_sale_price"], "15.00")
        self.assertEqual(line["sale_price"], "15.00")
        self.assertEqual(Decimal(line["markup_percent"]), Decimal("25.00"))
