"""ТЗ кассы 05.11 п.4–5: весовые строки в pos/checkout/."""
from decimal import Decimal

from apps.main.tests_tz_n15_checkout import CheckoutBase


class WeightLines1105Tests(CheckoutBase):
    def wprod(self):
        return self.mk(1, is_weight=True, unit="кг")[0]

    def test_two_identical_weight_lines(self):
        self.open_shift()
        p = self.wprod()
        line = {"product": str(p.id), "qty": "0.243", "price": "66.00"}
        r = self.co([line, dict(line)])
        self.assertIn(r.status_code, (201, 400), getattr(r, "data", r.content))
        self.assertEqual(r.status_code, 201, getattr(r, "data", None))
        self.assertEqual(len(r.data["items"]), 1)
        self.assertEqual(Decimal(r.data["items"][0]["qty"]), Decimal("0.486"))
        self.assertIn("lines_merged", [w["code"] for w in r.data.get("warnings") or []])

    def test_weight_line_total_matches_subtotal(self):
        self.open_shift()
        p1, p2 = self.wprod(), self.wprod()
        r = self.co([{"product": str(p1.id), "qty": "0.343", "price": "66.00"},
                     {"product": str(p2.id), "qty": "0.074", "price": "66.00"}])
        self.assertEqual(r.status_code, 201, getattr(r, "data", None))
        lines = sum(Decimal(i["line_total"]) for i in r.data["items"])
        lt = {i["product"]: Decimal(i["line_total"]) for i in r.data["items"]}
        self.assertEqual(lt[str(p1.id)], Decimal("22.63"))
        self.assertEqual(lt[str(p2.id)], Decimal("4.88"))
        self.assertEqual(lines, Decimal(r.data["subtotal"]))
        d = self.api.get(f"/api/main/pos/sales/{r.data['id']}/").json()
        self.assertEqual(sum(Decimal(str(i["line_total"])) for i in d["items"]), Decimal(d["subtotal"]))

    def test_duplicate_line_other_price_400(self):
        self.open_shift()
        p = self.wprod()
        r = self.co([{"product": str(p.id), "qty": "0.243", "price": "66.00"},
                     {"product": str(p.id), "qty": "0.100", "price": "70.00", "price_override": True}])
        self.assertEqual(r.status_code, 400, getattr(r, "data", None))
        self.assertEqual(r.data["code"], "duplicate_line")
