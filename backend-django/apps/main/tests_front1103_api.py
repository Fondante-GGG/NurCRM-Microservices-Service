"""03.11 front-market: сверка полей API с тем, что читает фронт (client_phone в чеке)."""
import uuid
from decimal import Decimal as D

from django.core.cache import cache
from django.test import TestCase
from rest_framework.test import APIClient

from apps.construction.models import Cashbox
from apps.main.models import Client, Sale
from apps.users.models import Company, SubscriptionPlan, User


class SaleClientPhoneTests(TestCase):
    def test_list_and_detail_have_client_phone(self):
        cache.clear()
        s = uuid.uuid4().hex[:6]
        owner = User.objects.create_user(email=f"o{s}@t.kg", password="x", role="owner")
        plan = SubscriptionPlan.objects.create(name="Pro", price=D("1"))
        company = Company.objects.create(name=f"A {s}", owner=owner, subscription_plan=plan)
        owner.company = company
        owner.save()
        cb = Cashbox.objects.create(company=company, name="K")
        cl = Client.objects.create(company=company, full_name="Айгуль", phone="+996555000111")
        sale = Sale.objects.create(company=company, user=owner, cashbox=cb, client=cl, payment_method="cash", status="paid", total=D("5"))
        Sale.objects.create(company=company, user=owner, cashbox=cb, payment_method="cash", status="paid", total=D("5"))
        api = APIClient()
        api.force_authenticate(owner)
        rows = api.get("/api/main/pos/sales/").data["results"]
        by = {str(r["id"]): r for r in rows}
        self.assertEqual(by[str(sale.id)]["client_phone"], "+996555000111")
        self.assertIsNone(next(r for k, r in by.items() if k != str(sale.id))["client_phone"])
        self.assertEqual(api.get(f"/api/main/pos/sales/{sale.id}/").data["client_phone"], "+996555000111")
