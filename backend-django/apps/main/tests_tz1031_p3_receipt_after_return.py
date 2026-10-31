"""ТЗ 31.10 п.3: чек не искажается после возврата.

pos/sales/{id}/ и список pos/sales/ отдают исходные строки, итог и оплаты; возврат —
отдельно (refunded_total, refunds[], returned_qty у строки, return_status). Деньги
(Sale.total в базе, строки оплаты, ящик смены) считаются как раньше.
"""
import uuid
from decimal import Decimal

from django.test import TestCase
from rest_framework.test import APIClient, force_authenticate

from apps.construction.models import CashShift
from apps.main.models import Product, Sale, SaleItem, SalePayment, SaleReturn
from apps.main.pos_views import SaleReturnAPIView
from apps.main import tests_pos_sale_return_cashflow as _base_mod

_Base = _base_mod.POSSaleReturnCashflowTests


class Tz1031P3ReceiptAfterReturnTests(TestCase):
    setUp = _Base.setUp

    def _sale_two_lines(self):
        """Чек: A 2×500 + B 1×300 = 1300, оплата наличными."""
        self.product_b = Product.objects.create(
            company=self.company, name="Товар Б", price=Decimal("300.00"), quantity=Decimal("10.00"),
        )
        sale = Sale.objects.create(
            company=self.company, branch=self.branch, cashbox=self.cashbox, shift=self.shift,
            user=self.cashier, payment_method="cash", status=Sale.Status.PAID,
            subtotal=Decimal("1300.00"), total=Decimal("1300.00"), cash_received=Decimal("1500.00"),
        )
        self.line_a = SaleItem.objects.create(
            company=self.company, branch=self.branch, sale=sale, product=self.product,
            unit_price=Decimal("500.00"), quantity=Decimal("2"), name_snapshot="Товар А",
        )
        self.line_b = SaleItem.objects.create(
            company=self.company, branch=self.branch, sale=sale, product=self.product_b,
            unit_price=Decimal("300.00"), quantity=Decimal("1"), name_snapshot="Товар Б",
        )
        SalePayment.objects.create(company=self.company, sale=sale, method="cash", amount=Decimal("1300.00"))
        return sale

    def _return(self, sale, lines=None, expect=200):
        body = {"idempotency_key": str(uuid.uuid4())}
        if lines:
            body["items"] = [{"sale_item_id": str(sid), "quantity": q} for sid, q in lines]
        req = self.factory.post(f"/main/pos/sales/{sale.id}/return/", body, format="json")
        force_authenticate(req, user=self.cashier)
        res = SaleReturnAPIView.as_view()(req, pk=sale.id)
        self.assertEqual(res.status_code, expect, getattr(res, "data", None))
        return res

    def _api(self):
        api = APIClient()
        api.force_authenticate(self.cashier)
        return api

    def _detail(self, sale):
        return self._api().get(f"/api/main/pos/sales/{sale.id}/").json()

    def _list_row(self, sale):
        lst = self._api().get("/api/main/pos/sales/").json()
        rows = lst["results"] if isinstance(lst, dict) else lst
        return next(r for r in rows if r["id"] == str(sale.id))

    def _drawer(self):
        return CashShift.objects.get(pk=self.shift.pk).calc_live_totals()["drawer_expected_cash"]

    def _assert_original(self, d, legacy=False):
        self.assertEqual(d["total"], "1300.00")
        self.assertEqual(d["subtotal"], "1300.00")
        # у старых возвратов «получено» восстанавливается обратным масштабом — до копейки
        self.assertAlmostEqual(Decimal(d["cash_received"]), Decimal("1500.00"), delta=Decimal("0.01") if legacy else 0)
        self.assertAlmostEqual(Decimal(d["change"]), Decimal("200.00"), delta=Decimal("0.01") if legacy else 0)
        by_id = {i["id"]: i for i in d["items"]}
        self.assertEqual(set(by_id), {str(self.line_a.id), str(self.line_b.id)})
        self.assertEqual(Decimal(by_id[str(self.line_a.id)]["quantity"]), Decimal("2"))
        self.assertEqual(by_id[str(self.line_a.id)]["amount"], "1000.00")
        self.assertEqual(Decimal(by_id[str(self.line_b.id)]["quantity"]), Decimal("1"))
        self.assertEqual([(p["method"], p["amount"]) for p in d["payments"]], [("cash", "1300.00")])
        return by_id

    def test_partial_then_full_return_keeps_original_receipt(self):
        sale = self._sale_two_lines()
        self._return(sale, [(self.line_a.id, 1)])

        d = self._detail(sale)
        by_id = self._assert_original(d)
        self.assertEqual(d["status"], "partially_returned")
        self.assertEqual(d["return_status"], "partial")
        self.assertEqual(d["refunded_total"], "500.00")
        self.assertEqual(d["net_total"], "800.00")
        self.assertEqual(d["refundable_total"], "800.00")
        self.assertEqual(by_id[str(self.line_a.id)]["returned_qty"], "1.000")
        self.assertEqual(Decimal(str(by_id[str(self.line_a.id)]["returnable_qty"])), Decimal("1"))
        self.assertEqual(len(d["refunds"]), 1)
        self.assertEqual(d["refunds"][0]["amount"], "500.00")
        self.assertEqual(d["refunds"][0]["lines"][0]["sale_item"], str(self.line_a.id))

        self._return(sale)  # полный возврат остатка
        d = self._detail(sale)
        by_id = self._assert_original(d)
        self.assertEqual(d["status"], "canceled")
        self.assertEqual(d["return_status"], "full")
        self.assertEqual(d["refunded_total"], "1300.00")
        self.assertEqual(d["net_total"], "0.00")
        self.assertEqual(d["refundable_total"], "0.00")
        self.assertEqual(by_id[str(self.line_a.id)]["returned_qty"], "2.000")
        self.assertEqual(by_id[str(self.line_b.id)]["returned_qty"], "1.000")
        self.assertEqual([r["amount"] for r in d["refunds"]], ["500.00", "800.00"])
        for key in ("id", "amount", "cash", "noncash", "created_at", "lines"):
            self.assertIn(key, d["refunds"][1])

        row = self._list_row(sale)
        self.assertEqual(row["total"], "1300.00")
        self.assertEqual(row["refunded_total"], "1300.00")
        self.assertEqual(row["net_total"], "0.00")
        self.assertEqual(row["items_count"], 2)

        # Повторный полный возврат по-прежнему запрещён
        self._return(sale, expect=400)

    def test_returns_by_lines_until_empty_keep_items(self):
        """Случай из ТЗ: раньше после возврата всех строк было total: остаток, items: []."""
        sale = self._sale_two_lines()
        self._return(sale, [(self.line_a.id, 1)])
        self._return(sale, [(self.line_a.id, 1), (self.line_b.id, 1)])
        self.assertFalse(SaleItem.objects.filter(sale=sale).exists())  # модель — как раньше

        d = self._detail(sale)
        by_id = self._assert_original(d)
        self.assertEqual(d["refunded_total"], "1300.00")
        self.assertEqual(d["return_status"], "full")
        self.assertEqual(by_id[str(self.line_a.id)]["returned_qty"], "2.000")
        self.assertEqual(by_id[str(self.line_a.id)]["product_name"], "Товар А")
        self.assertEqual(len(d["refunds"]), 2)

    def test_legacy_returns_without_snapshot_are_restored(self):
        """Возвраты до 31.10 (без sale_before) — исходный чек восстанавливается по returned_items."""
        sale = self._sale_two_lines()
        self._return(sale, [(self.line_a.id, 1)])
        SaleReturn.objects.filter(sale=sale).update(sale_before=None)
        d = self._detail(sale)
        self._assert_original(d, legacy=True)
        self.assertEqual(d["refunded_total"], "500.00")

        self._return(sale, [(self.line_a.id, 1), (self.line_b.id, 1)])
        SaleReturn.objects.filter(sale=sale).update(sale_before=None)
        d = self._detail(sale)
        self._assert_original(d, legacy=True)
        self.assertEqual(d["refunded_total"], "1300.00")

    def test_money_unchanged_by_representation(self):
        """Деньги в базе и в смене — как до правки: итог уменьшается, оплата масштабируется, ящик падает."""
        sale = self._sale_two_lines()
        self.assertEqual(self._drawer(), Decimal("1800.00"))  # 500 размен + 1300
        self._return(sale, [(self.line_a.id, 1)])
        sale.refresh_from_db()
        self.assertEqual(sale.total, Decimal("800.00"))
        self.assertEqual(SaleItem.objects.get(pk=self.line_a.pk).quantity, Decimal("1"))
        self.assertEqual(sum(p.amount for p in sale.payments.all()), Decimal("800.00"))
        self.assertEqual(self._drawer(), Decimal("1300.00"))
        self._return(sale)
        sale.refresh_from_db()
        self.assertEqual(sale.status, Sale.Status.CANCELED)
        self.assertEqual(self._drawer(), Decimal("500.00"))
        self.assertEqual(
            sum(r.returned_amount for r in SaleReturn.objects.filter(sale=sale)), Decimal("1300.00")
        )

    def test_public_receipt_not_doubled(self):
        from apps.main.media_receipts import receipt_public_data
        from apps.main.models import SaleReceiptLink

        sale = self._sale_two_lines()
        self._return(sale, [(self.line_a.id, 1)])
        link = SaleReceiptLink.objects.create(sale=sale, company=self.company)
        data = receipt_public_data(link)
        self.assertEqual(len(data["items"]), 2)
        self.assertEqual(data["totals"]["total"], "1300.00")
        self.assertEqual(data["totals"]["purchase_total"], "1300.00")
        self.assertEqual(data["totals"]["returned_total"], "500.00")
        self.assertEqual(data["totals"]["to_pay"], "800.00")
        self.assertEqual(data["status"], "partially_returned")

        self._return(sale)
        data = receipt_public_data(SaleReceiptLink.objects.get(pk=link.pk))
        self.assertEqual(len(data["items"]), 2)
        self.assertTrue(all(i["returned"] for i in data["items"]))
        self.assertEqual(data["totals"]["purchase_total"], "1300.00")
        self.assertEqual(data["totals"]["to_pay"], "0.00")
        self.assertEqual(data["status"], "returned")

    def test_sale_without_returns_unchanged(self):
        sale = self._sale_two_lines()
        d = self._detail(sale)
        self._assert_original(d)
        self.assertEqual(d["refunds"], [])
        self.assertEqual(d["refunded_total"], "0.00")
        self.assertEqual(d["return_status"], "none")
        self.assertEqual(d["net_total"], "1300.00")


del _Base, _base_mod  # чтобы загрузчик тестов не собрал базовый класс второй раз
