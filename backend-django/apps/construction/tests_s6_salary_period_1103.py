"""S6 (аудит 03.11): CashFlow.salary_period — "YYYY-MM" или {from, to}, фильтр, выплаты зарплаты."""
import uuid
from datetime import date

from django.core.cache import cache
from django.test import TestCase
from rest_framework.test import APIClient

from apps.construction.models import Cashbox, CashFlow
from apps.users.models import Company, User

URL = "/api/construction/cashflows/"


class SalaryPeriodTests(TestCase):
    def setUp(self):
        cache.clear()
        s = uuid.uuid4().hex[:6]
        self.owner = User.objects.create_user(email=f"o{s}@t.kg", password="x", role="owner")
        self.company = Company.objects.create(name=f"Co {s}", owner=self.owner)
        self.owner.company = self.company
        self.owner.save()
        self.cb = Cashbox.objects.create(company=self.company, name="Касса", role=Cashbox.CashboxRole.POS_MAIN)
        self.emp = User.objects.create_user(email=f"e{s}@t.kg", password="x", company=self.company,
                                            first_name="Айбек")
        self.api = APIClient()
        self.api.force_authenticate(self.owner)

    def post(self, **extra):
        body = {"cashbox": str(self.cb.id), "type": "expense", "name": "Зарплата: Айбек", "amount": "100.00",
                "employee": str(self.emp.id), **extra}
        return self.api.post(URL, body, format="json")

    def names(self, **q):
        r = self.api.get(URL, q)
        self.assertEqual(r.status_code, 200, r.content)
        return sorted(x["amount"] for x in r.json()["results"])

    def test_month_string(self):
        r = self.post(salary_period="2026-10")
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(r.json()["salary_period"], "2026-10")
        f = CashFlow.objects.get(pk=r.json()["id"])
        self.assertEqual((f.salary_period_from, f.salary_period_to), (date(2026, 10, 1), date(2026, 10, 31)))

    def test_from_to_and_patch_clear(self):
        r = self.post(salary_period={"from": "2026-10-01", "to": "2026-10-15"})
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(r.json()["salary_period"], {"from": "2026-10-01", "to": "2026-10-15"})
        fid = r.json()["id"]
        r = self.api.patch(f"{URL}{fid}/", {"salary_period": "2026-09"}, format="json")
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(r.json()["salary_period"], "2026-09")
        r = self.api.patch(f"{URL}{fid}/", {"salary_period": None}, format="json")
        self.assertEqual(r.status_code, 200, r.content)
        self.assertIsNone(r.json()["salary_period"])
        self.assertIsNone(CashFlow.objects.get(pk=fid).salary_period_from)

    def test_without_field_as_before(self):
        r = self.post()
        self.assertEqual(r.status_code, 201, r.content)
        self.assertIsNone(r.json()["salary_period"])
        fid = r.json()["id"]
        CashFlow.objects.filter(pk=fid).update(salary_period_from=date(2026, 8, 1), salary_period_to=date(2026, 8, 31))
        r = self.api.patch(f"{URL}{fid}/", {"name": "Зарплата: Айбек (аванс)"}, format="json")
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(r.json()["salary_period"], "2026-08")  # PATCH без поля период не трогает

    def test_invalid(self):
        for bad in ("2026-13", "10.2026", {"from": "2026-10-20", "to": "2026-10-01"}, {"from": "xx"}, 5):
            r = self.post(salary_period=bad)
            self.assertEqual(r.status_code, 400, (bad, r.content))
            self.assertIn("salary_period", r.json().get("fields", r.json()), r.content)

    def test_filter(self):
        self.post(amount="1.00", salary_period="2026-09")
        self.post(amount="2.00", salary_period="2026-10")
        self.post(amount="3.00", salary_period={"from": "2026-09-20", "to": "2026-10-05"})
        self.post(amount="4.00")
        self.assertEqual(self.names(salary_period="2026-10"), ["2.00", "3.00"])
        self.assertEqual(self.names(salary_period="2026-09"), ["1.00", "3.00"])
        self.assertEqual(self.names(salary_period_from="2026-10-10", salary_period_to="2026-12-31"), ["2.00"])
        self.assertEqual(len(self.names()), 4)
        self.assertEqual(self.api.get(URL, {"salary_period": "bad"}).status_code, 400)

    def test_market_salary_payout_sets_period(self):
        r = self.api.post("/api/main/market-salary/payouts/", {
            "employee": str(self.emp.id), "amount": "500", "cashbox": str(self.cb.id),
            "period_from": "2026-10-01", "period_to": "2026-10-31",
        }, format="json")
        self.assertIn(r.status_code, (200, 201), r.content)
        f = CashFlow.objects.filter(employee=self.emp).order_by("-created_at").first()
        self.assertIsNotNone(f, r.content)
        self.assertEqual((f.salary_period_from, f.salary_period_to), (date(2026, 10, 1), date(2026, 10, 31)))
