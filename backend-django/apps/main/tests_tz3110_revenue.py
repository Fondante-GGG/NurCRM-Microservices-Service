"""ТЗ 31.10 п.11: единое определение выручки и строки чеков пачкой."""
import uuid
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.construction.models import Cashbox
from apps.main.models import Product, Sale, SaleItem
from apps.users.models import Company, User

D = Decimal


class RevenueTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(email=f"o{uuid.uuid4().hex[:6]}@t.kg", password="x", role="owner")
        self.company = Company.objects.create(name="Co", owner=self.owner)
        self.owner.company = self.company
        self.owner.save()
        self.cb = Cashbox.objects.create(company=self.company, name="Касса")
        self.p = Product.objects.create(company=self.company, name="Сок", quantity=D("10"),
                                        purchase_price=D("10.00"), price=D("100.00"))
        now = timezone.now()

        def sale(status, total, paid=True, **kw):
            s = Sale.objects.create(company=self.company, cashbox=self.cb, user=self.owner, status=status,
                                    payment_method="cash", total=total, paid_at=now if paid else None, **kw)
            SaleItem.objects.create(sale=s, company=self.company, product=self.p, name_snapshot="Сок",
                                    unit_price=total, quantity=D("1.000"), purchase_price_snapshot=D("10.00"))
            return s

        self.paid = sale(Sale.Status.PAID, D("100.00"))
        self.debt = sale(Sale.Status.DEBT, D("300.00"), paid=False)
        self.canceled = sale(Sale.Status.CANCELED, D("999.00"), paid=False)
        self.api = APIClient()
        self.api.force_authenticate(self.owner)
        self.d = timezone.localdate().isoformat()

    def _tab(self, tab):
        r = self.api.get("/api/main/analytics/market/", {"tab": tab, "date_from": self.d, "date_to": self.d})
        self.assertEqual(r.status_code, 200, getattr(r, "data", None))
        return r.data

    def test_pnl_includes_debt_excludes_canceled(self):
        d = self._tab("pnl")
        self.assertEqual(d["revenue"], "400.00")
        self.assertEqual(d["definition"]["code"], "sales_total_minus_returns_v1")

    def test_abc_receipts_revenue_matches_and_has_definition(self):
        d = self._tab("abc")
        self.assertEqual(d["totals"]["receipts_revenue"], "400.00")
        self.assertEqual(d["definition"]["code"], "sales_total_minus_returns_v1")

    def test_sales_summary_sales_total(self):
        d = self._tab("sales")
        self.assertEqual(d["cards"]["sales_total"], "400.00")
        self.assertEqual(d["definition"]["code"], "sales_total_minus_returns_v1")
        # revenue в «Продажах» — деньги (долг без предоплаты не входит), как и раньше
        self.assertEqual(d["cards"]["revenue"], "100.00")

    def test_sale_items_batch(self):
        r = self.api.get("/api/main/pos/sales/items/", {"date_from": self.d, "date_to": self.d})
        self.assertEqual(r.status_code, 200, getattr(r, "data", None))
        self.assertEqual(r.data["limit"], 1000)
        self.assertEqual(r.data["count"], 3)
        row = r.data["results"][0]
        for key in ("sale_id", "doc_number", "created_at", "product", "name", "qty", "price", "discount", "total"):
            self.assertIn(key, row)
        r = self.api.get("/api/main/pos/sales/items/", {"limit": 2, "offset": 2, "date_from": self.d, "date_to": self.d})
        self.assertEqual(len(r.data["results"]), 1)
        r = self.api.get("/api/main/pos/sales/items/", {"limit": 99999})
        self.assertEqual(r.data["limit"], 5000)

    def test_sale_items_company_isolation(self):
        o2 = User.objects.create_user(email=f"x{uuid.uuid4().hex[:6]}@t.kg", password="x", role="owner")
        c2 = Company.objects.create(name="Other", owner=o2)
        o2.company = c2
        o2.save()
        a2 = APIClient()
        a2.force_authenticate(o2)
        r = a2.get("/api/main/pos/sales/items/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["count"], 0)
