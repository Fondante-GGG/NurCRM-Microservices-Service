"""03.11 front-market: серверные фильтры — чеки «Безнал» (payment_method=noncash / список), приходы «кто / сумма / товар»."""
import uuid
from decimal import Decimal as D

from django.core.cache import cache
from django.test import TestCase
from rest_framework.test import APIClient

from apps.main.models import Client, Product, Sale, SupplierReceipt, SupplierReceiptItem
from apps.users.models import Company, SubscriptionPlan, User


class Base(TestCase):
    def setUp(self):
        cache.clear()
        s = uuid.uuid4().hex[:6]
        self.owner = User.objects.create_user(email=f"o{s}@t.kg", password="x", role="owner", first_name="Влад")
        plan = SubscriptionPlan.objects.create(name="Pro", price=D("100.00"))
        self.company = Company.objects.create(name=f"F {s}", owner=self.owner, subscription_plan=plan)
        self.owner.company = self.company
        self.owner.save()
        self.clerk = User.objects.create_user(email=f"c{s}@t.kg", password="x", role="cashier", company=self.company, first_name="Кассир")
        self.api = APIClient()
        self.api.force_authenticate(self.owner)

    def rows(self, url, **q):
        r = self.api.get(url, q)
        self.assertEqual(r.status_code, 200, getattr(r, "data", None))
        return r.data, (r.data["results"] if isinstance(r.data, dict) else r.data)


class SalesNoncashTests(Base):
    def test_noncash_and_csv(self):
        from apps.construction.models import Cashbox

        cb = Cashbox.objects.create(company=self.company, name="Касса")
        for m in ("cash", "transfer", "mbank", "optima", "obank", "bakai", "debt", "mixed", "offset"):
            Sale.objects.create(company=self.company, user=self.owner, cashbox=cb, payment_method=m, status=Sale.Status.PAID, total=D("10"))
        url = "/api/main/pos/sales/"
        _, rows = self.rows(url, payment_method="noncash", limit=50)
        self.assertEqual(sorted(r["payment_method"] for r in rows), sorted(["transfer", "mbank", "optima", "obank", "bakai", "mixed", "offset"]))
        _, rows = self.rows(url, payment_method="transfer", limit=50)
        self.assertEqual(len(rows), 5)  # как раньше: перевод = все банки
        _, rows = self.rows(url, payment_method="cash,debt", limit=50)
        self.assertEqual(sorted(r["payment_method"] for r in rows), ["cash", "debt"])
        _, rows = self.rows(url, payment_method="cash", limit=50)
        self.assertEqual(len(rows), 1)


class ReceiptFiltersTests(Base):
    def setUp(self):
        super().setUp()
        self.sup = Client.objects.create(full_name="Альфа", type=Client.StatusClient.SUPPLIERS, company=self.company)
        self.cola = Product.objects.create(name="Кола", barcode="4870001", company=self.company, price=D("20"))
        self.tea = Product.objects.create(name="Чай", barcode="4870002", company=self.company, price=D("20"))
        self.r1 = self._receipt(self.owner, [(self.cola, "2", "50")])  # 100
        self.r2 = self._receipt(self.clerk, [(self.tea, "10", "50"), (self.cola, "1", "5")])  # 505
        self.r3 = self._receipt(self.clerk, [(self.tea, "1", "30")])  # 30

    def _receipt(self, who, lines):
        r = SupplierReceipt.objects.create(company=self.company, supplier=self.sup, created_by=who)
        for p, q, price in lines:
            SupplierReceiptItem.objects.create(receipt=r, product=p, qty=D(q), purchase_price=D(price))
        return r

    def ids(self, **q):
        data, rows = self.rows("/api/main/suppliers/receipts/", **q)
        return {str(r["id"]) for r in rows}, data

    def test_created_by(self):
        got, _ = self.ids(created_by=str(self.clerk.id))
        self.assertEqual(got, {str(self.r2.id), str(self.r3.id)})
        got, _ = self.ids(created_by="bad")
        self.assertEqual(got, set())

    def test_amount_min_max_and_total(self):
        got, data = self.ids(amount_min="100")
        self.assertEqual(got, {str(self.r1.id), str(self.r2.id)})
        self.assertEqual(data["count"], 2)
        self.assertEqual(D(str(data["meta"]["total_amount"])), D("605.00"))
        got, _ = self.ids(amount_min="50", amount_max="200,5")
        self.assertEqual(got, {str(self.r1.id)})
        got, _ = self.ids(amount_min="abc")
        self.assertEqual(got, set())

    def test_product_search_keeps_all_lines(self):
        got, data = self.ids(product_search="Кол")  # sqlite: регистр не важен только для латиницы
        self.assertEqual(got, {str(self.r1.id), str(self.r2.id)})
        got, data = self.ids(product_search="4870001")
        self.assertEqual(got, {str(self.r1.id), str(self.r2.id)})
        r2 = next(r for r in data["results"] if str(r["id"]) == str(self.r2.id))
        self.assertEqual(len(r2["items"]), 2)  # в отличие от product_id, строки прихода не урезаются
        got, _ = self.ids(product_search="4870002", created_by=str(self.clerk.id), amount_min="100")
        self.assertEqual(got, {str(self.r2.id)})


class CapabilitiesTests(Base):
    def test_features(self):
        r = self.api.get("/api/main/capabilities/")
        self.assertEqual(r.status_code, 200)
        for f in ("cashflow_employee", "product_thumbs", "sales_noncash_filter", "receipts_filters"):
            self.assertIn(f, r.data["features"])
