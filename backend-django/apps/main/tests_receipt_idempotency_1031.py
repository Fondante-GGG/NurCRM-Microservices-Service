"""31.10: повтор прихода с тем же Idempotency-Key не проводит второй приход (и без create_deal)."""
from decimal import Decimal
import uuid

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.main.models import Client, Product, SupplierReceipt
from apps.users.models import Company, SubscriptionPlan

User = get_user_model()


class ReceiptIdempotencyTests(TestCase):
    def setUp(self):
        self.api = APIClient()
        self.owner = User.objects.create_user(email=f"o_{uuid.uuid4().hex[:6]}@t.com", password="pass", role="owner")
        plan = SubscriptionPlan.objects.create(name="Pro", price=Decimal("100.00"))
        self.company = Company.objects.create(name="Co", owner=self.owner, subscription_plan=plan)
        self.owner.company = self.company
        self.owner.save()
        self.api.force_authenticate(user=self.owner)
        self.supplier = Client.objects.create(full_name="Альфа", type=Client.StatusClient.SUPPLIERS, company=self.company)
        self.product = Product.objects.create(name="Печенье", company=self.company, quantity=Decimal("10"),
                                              purchase_price=Decimal("40.00"), price=Decimal("60.00"), markup_percent=Decimal("50.00"))
        self.url = f"/api/main/suppliers/{self.supplier.id}/receipt/"
        self.body = {"items": [{"product": str(self.product.id), "qty": 5, "purchase_price": "40.00"}]}

    def test_same_key_header_no_second_receipt(self):
        r1 = self.api.post(self.url, self.body, format="json", HTTP_IDEMPOTENCY_KEY="k-1")
        r2 = self.api.post(self.url, self.body, format="json", HTTP_IDEMPOTENCY_KEY="k-1")
        self.assertIn(r1.status_code, (200, 201), r1.data)
        self.assertEqual(r2.status_code, r1.status_code)
        self.assertTrue(r2.data.get("replayed"))
        self.assertEqual(SupplierReceipt.objects.filter(company=self.company).count(), 1)
        self.product.refresh_from_db()
        self.assertEqual(self.product.quantity, Decimal("15"))

    def test_same_key_in_body_no_second_receipt(self):
        body = {**self.body, "idempotency_key": "k-2"}
        self.api.post(self.url, body, format="json")
        self.api.post(self.url, body, format="json")
        self.assertEqual(SupplierReceipt.objects.filter(company=self.company).count(), 1)

    def test_without_key_works_as_before(self):
        self.api.post(self.url, self.body, format="json")
        self.api.post(self.url, self.body, format="json")
        self.assertEqual(SupplierReceipt.objects.filter(company=self.company).count(), 2)
