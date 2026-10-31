"""ТЗ 31.10 п.19: закупка с 4 знаками, сумма строки прихода по накладной, остатки ревизии с 3 знаками."""
from decimal import Decimal
import uuid

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.main.models import Client, ClientDeal, Product, SupplierReceiptItem
from apps.users.models import Company, SubscriptionPlan

User = get_user_model()


class PurchasePrecisionTests(TestCase):
    def setUp(self):
        self.api = APIClient()
        self.owner = User.objects.create_user(email=f"o_{uuid.uuid4().hex[:6]}@t.com", password="pass", role="owner")
        plan = SubscriptionPlan.objects.create(name="Pro", price=Decimal("100.00"))
        self.company = Company.objects.create(name="Co", owner=self.owner, subscription_plan=plan)
        self.owner.company = self.company
        self.owner.save()
        self.api.force_authenticate(user=self.owner)
        self.supplier = Client.objects.create(full_name="Альфа", type=Client.StatusClient.SUPPLIERS, company=self.company)
        self.product = Product.objects.create(name="Гвозди", company=self.company, quantity=Decimal("0"),
                                              purchase_price=Decimal("10.00"), price=Decimal("20.00"))
        self.url = f"/api/main/suppliers/{self.supplier.id}/receipt/"

    def test_product_patch_purchase_price_4_digits(self):
        r = self.api.patch(f"/api/main/products/{self.product.id}/", {"purchase_price": "12.3456"}, format="json")
        self.assertEqual(r.status_code, 200, r.data)
        self.product.refresh_from_db()
        self.assertEqual(self.product.purchase_price, Decimal("12.3456"))
        self.assertEqual(r.data["purchase_price"], "12.3456")

    def test_product_price_output_keeps_two_digits(self):
        r = self.api.get(f"/api/main/products/{self.product.id}/")
        self.assertEqual(r.data["purchase_price"], "10.00")

    def test_update_rounds_to_4_digits(self):
        Product.objects.filter(pk=self.product.pk).update(purchase_price=Decimal("1.234567"))
        self.product.refresh_from_db()
        self.assertEqual(self.product.purchase_price, Decimal("1.2346"))

    def test_receipt_line_4_digits_accepted(self):
        body = {"items": [{"product": str(self.product.id), "qty": 3, "purchase_price": "12.3456"}]}
        r = self.api.post(self.url, body, format="json")
        self.assertEqual(r.status_code, 200, r.data)
        item = SupplierReceiptItem.objects.get(receipt_id=r.data["id"])
        self.assertEqual(item.purchase_price, Decimal("12.3456"))
        self.product.refresh_from_db()
        self.assertEqual(self.product.purchase_price, Decimal("12.3456"))

    def test_line_total_as_in_document(self):
        body = {
            "create_deal": True, "payment_type": "debt",
            "items": [{"product": str(self.product.id), "qty": 100, "purchase_price": "12.345", "line_total": "1234.50"}],
        }
        r = self.api.post(self.url, body, format="json")
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data["total_amount"], "1234.50")
        self.assertEqual(r.data["debt_amount"], "1234.50")
        deal = ClientDeal.objects.get(id=r.data["deal_id"])
        self.assertEqual(deal.amount, Decimal("1234.50"))
        g = self.api.get(f"/api/main/suppliers/receipts/{r.data['id']}/")
        self.assertEqual(g.data["total_amount"], "1234.50")
        self.assertEqual(g.data["items"][0]["line_total"], "1234.50")
        self.assertEqual(g.data["items"][0]["purchase_price"], "12.345")
        lst = self.api.get("/api/main/suppliers/receipts/")
        self.assertEqual(lst.data["meta"]["total_amount"], "1234.50")

    def test_line_total_without_price_gives_price(self):
        body = {"items": [{"product": str(self.product.id), "qty": 3, "line_total": "100.00"}]}
        r = self.api.post(self.url, body, format="json")
        self.assertEqual(r.status_code, 200, r.data)
        item = SupplierReceiptItem.objects.get(receipt_id=r.data["id"])
        self.assertEqual(item.purchase_price, Decimal("33.3333"))
        self.assertEqual(item.line_total, Decimal("100.00"))

    def test_without_line_total_as_before(self):
        body = {"create_deal": True, "payment_type": "debt",
                "items": [{"product": str(self.product.id), "qty": 100, "purchase_price": "12.35"}]}
        r = self.api.post(self.url, body, format="json")
        self.assertEqual(r.data["total_amount"], "1235.00")

    def test_inventory_quantity_fact_3_digits(self):
        r = self.api.post("/api/main/inventory/sessions/", {
            "items": [{"product_id": str(self.product.id), "quantity_fact": "1.234"}],
        }, format="json")
        self.assertEqual(r.status_code, 201, r.data)
        a = self.api.post(f"/api/main/inventory/sessions/{r.data['id']}/apply/", {}, format="json")
        self.assertEqual(a.status_code, 200, a.data)
        self.product.refresh_from_db()
        self.assertEqual(self.product.quantity, Decimal("1.234"))
