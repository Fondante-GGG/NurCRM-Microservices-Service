"""ТЗ кассы 05.11 п.2–3: возврат чека в долг, частично погашенного наличными."""
import uuid
from decimal import Decimal

from apps.main.models import Product, Sale, SaleItem
from apps.main.tests_tz1029_b13_debt import B13Base


class DebtSaleReturn1105Tests(B13Base):
    def setUp(self):
        super().setUp()
        p = Product.objects.create(company=self.company, name="Т", price=Decimal("100.00"),
                                   purchase_price=Decimal("50.00"), quantity=Decimal("5"))
        SaleItem.objects.create(sale=self.sale, product=p, name_snapshot="Т", unit_price=Decimal("100.00"),
                                quantity=Decimal("1"))

    def ret(self, sh, **body):
        body.setdefault("idempotency_key", str(uuid.uuid4()))
        body.setdefault("shift", str(sh.id))
        body.setdefault("cashbox", str(self.pos_box.id))
        return self.api.post(f"/api/main/pos/sales/{self.sale.id}/return/", body, format="json")

    def test_full_return_takes_repaid_cash_from_drawer(self):
        sh = self.shift(self.owner)
        r = self.pay(amount="30.00", shift=str(sh.id))
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(self.expected(sh), Decimal("30.00"))
        r = self.ret(sh)
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(self.expected(sh), Decimal("0.00"))
        # п.3: поля долга самого чека
        d = self.api.get(f"/api/main/pos/sales/{self.sale.id}/").json()
        self.assertEqual(d["status"], "canceled")
        for f in ("remaining_debt", "debt_remaining", "debt_amount"):
            if f in d and d[f] is not None:
                self.assertEqual(Decimal(d[f]), Decimal("0.00"), f)
        # повтор возврата не снимает второй раз
        self.ret(sh)
        self.assertEqual(self.expected(sh), Decimal("0.00"))

    def test_unpaid_debt_return_no_drawer_change(self):
        sh = self.shift(self.owner)
        r = self.ret(sh)
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(self.expected(sh), Decimal("0.00"))
        self.sale.refresh_from_db()
        self.assertEqual(self.sale.debt_remaining, Decimal("0.00"))

    def test_sale_pay_debt_then_return(self):
        sh = self.shift(self.owner)
        r = self.api.post(f"/api/main/pos/sales/{self.sale.id}/pay-debt/",
                          {"amount": "20.00", "payment_method": "cash", "shift": str(sh.id)}, format="json",
                          HTTP_IDEMPOTENCY_KEY=str(uuid.uuid4()))
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(self.expected(sh), Decimal("20.00"))
        r = self.ret(sh)
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(self.expected(sh), Decimal("0.00"))
