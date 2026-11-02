"""03.11 front-market: CashFlow.employee — кому выплачена зарплата, фильтр ?employee=, команда заполнения."""
import uuid
from decimal import Decimal as D
from io import StringIO

from django.core.cache import cache
from django.core.management import call_command
from django.test import TestCase
from rest_framework.test import APIClient

from apps.construction.models import Cashbox, CashFlow
from apps.users.models import Company, User

URL = "/api/construction/cashflows/"


class CashFlowEmployeeTests(TestCase):
    def setUp(self):
        cache.clear()
        s = uuid.uuid4().hex[:6]
        self.owner = User.objects.create_user(email=f"o{s}@t.kg", password="x", role="owner")
        self.company = Company.objects.create(name=f"Co {s}", owner=self.owner)
        self.owner.company = self.company
        self.owner.save()
        self.cb = Cashbox.objects.create(company=self.company, name="Касса", role=Cashbox.CashboxRole.POS_MAIN)
        self.emp = User.objects.create_user(email=f"e{s}@t.kg", password="x", role="cashier", company=self.company,
                                            first_name="Айбек", last_name="Асанов")
        self.other_owner = User.objects.create_user(email=f"x{s}@t.kg", password="x", role="owner")
        self.other = Company.objects.create(name=f"Other {s}", owner=self.other_owner)
        self.stranger = User.objects.create_user(email=f"s{s}@t.kg", password="x", role="cashier", company=self.other)
        self.api = APIClient()
        self.api.force_authenticate(self.owner)

    def _rows(self, **q):
        r = self.api.get(URL, q)
        self.assertEqual(r.status_code, 200, getattr(r, "data", None))
        return r.data["results"] if isinstance(r.data, dict) else r.data

    def test_create_with_employee_list_and_filter(self):
        r = self.api.post(URL, {"cashbox": str(self.cb.id), "type": "expense", "name": "Зарплата: Айбек Асанов",
                                "amount": "100.00", "employee": str(self.emp.id)}, format="json")
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(r.data["employee"], self.emp.id)
        self.assertEqual(r.data["employee_name"], "Айбек Асанов")
        self.api.post(URL, {"cashbox": str(self.cb.id), "type": "expense", "name": "Аренда", "amount": "5.00"}, format="json")

        rows = self._rows(employee=str(self.emp.id))
        self.assertEqual([x["name"] for x in rows], ["Зарплата: Айбек Асанов"])
        self.assertEqual(str(rows[0]["employee"]), str(self.emp.id))
        # старое поведение ТЗ Н-19: строки без employee ищутся по кассиру
        self.assertEqual({x["name"] for x in self._rows(employee=str(self.owner.id))}, {"Аренда"})
        self.assertEqual(self._rows(employee=str(self.owner.id), employee_strict="1"), [])
        self.assertEqual(self.api.get(URL, {"employee": "bad"}).status_code, 400)

    def test_employee_of_other_company_rejected(self):
        r = self.api.post(URL, {"cashbox": str(self.cb.id), "type": "expense", "name": "Зарплата: X",
                                "amount": "1.00", "employee": str(self.stranger.id)}, format="json")
        self.assertEqual(r.status_code, 400)
        self.assertIn("employee", r.data if isinstance(r.data, dict) else {})

    def test_old_client_without_employee_still_works(self):
        r = self.api.post(URL, {"cashbox": str(self.cb.id), "type": "expense", "name": "Зарплата: Айбек Асанов",
                                "amount": "1.00"}, format="json")
        self.assertEqual(r.status_code, 201, r.data)
        self.assertIsNone(r.data["employee"])
        self.assertIsNone(r.data["employee_name"])

    def test_backfill_by_name_dry_run_then_apply(self):
        f1 = CashFlow.objects.create(company=self.company, cashbox=self.cb, type="expense", amount=D("10"),
                                     name="Зарплата: Айбек  Асанов · аванс", status="approved")
        f2 = CashFlow.objects.create(company=self.company, cashbox=self.cb, type="expense", amount=D("10"),
                                     name="Зарплата: Нет Такого", status="approved")
        User.objects.create_user(email=f"d1{uuid.uuid4().hex[:4]}@t.kg", password="x", company=self.company,
                                 first_name="Дубль", last_name="Имя", role="cashier")
        User.objects.create_user(email=f"d2{uuid.uuid4().hex[:4]}@t.kg", password="x", company=self.company,
                                 first_name="Дубль", last_name="Имя", role="cashier")
        f3 = CashFlow.objects.create(company=self.company, cashbox=self.cb, type="expense", amount=D("10"),
                                     name="Зарплата: Дубль Имя", status="approved")
        out = StringIO()
        call_command("backfill_cashflow_employee", stdout=out)
        self.assertIn("dry-run", out.getvalue())
        self.assertIsNone(CashFlow.objects.get(pk=f1.pk).employee_id)

        out = StringIO()
        call_command("backfill_cashflow_employee", "--apply", "--batch", "1", "--sleep", "0", stdout=out)
        self.assertEqual(CashFlow.objects.get(pk=f1.pk).employee_id, self.emp.id)
        self.assertIsNone(CashFlow.objects.get(pk=f2.pk).employee_id)
        self.assertIsNone(CashFlow.objects.get(pk=f3.pk).employee_id)
        self.assertIn("по имени 1", out.getvalue())
        self.assertIn("имя у нескольких сотрудников 1", out.getvalue())


class MarketSalaryPayoutEmployeeTests(TestCase):
    def test_payout_sets_employee_on_cashflow_and_reversal(self):
        from apps.construction.models import Cashbox as CB
        from apps.main.models import Branch, MarketSalaryPayout, MarketSaleEmployeePayProfile

        cache.clear()
        s = uuid.uuid4().hex[:6]
        owner = User.objects.create_user(email=f"o{s}@t.kg", password="x", role="owner")
        company = Company.objects.create(name=f"N18e {s}", owner=owner)
        owner.company = company
        owner.save()
        branch = Branch.objects.create(name="Main", company=company)
        pos = CB.objects.create(name="Касса", role=CB.CashboxRole.POS_MAIN, company=company, branch=branch)
        emp = User.objects.create_user(email=f"c{s}@t.kg", password="x", role="cashier", company=company)
        MarketSaleEmployeePayProfile.objects.create(company=company, user=emp, pay_scheme="salary", monthly_base_salary=D("3000"))
        api = APIClient()
        api.force_authenticate(owner)
        r = api.post("/main/market-salary/payouts/", {"employee": str(emp.id), "kind": "salary", "amount": "1.00",
                                                      "cashbox": str(pos.id)}, format="json")
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(CashFlow.objects.get(pk=r.data["cashflow_id"]).employee_id, emp.id)
        self.assertEqual(api.delete(f"/main/market-salary/payouts/{r.data['id']}/").status_code, 200)
        p = MarketSalaryPayout.objects.get(pk=r.data["id"])
        self.assertEqual(p.reversal_cashflow.employee_id, emp.id)

        # команда заполнения находит сотрудника по id выплаты
        CashFlow.objects.filter(source_kind="salary_payout").update(employee=None)
        call_command("backfill_cashflow_employee", "--apply", "--sleep", "0", stdout=StringIO())
        self.assertEqual(set(CashFlow.objects.filter(source_kind="salary_payout").values_list("employee_id", flat=True)), {emp.id})
