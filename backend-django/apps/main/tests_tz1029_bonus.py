from decimal import Decimal

from apps.main.models import ClientBonusTransaction as T
from apps.main.tests_kassa_api import KassaBase


class BonusTz1029Tests(KassaBase):
    def test_summary_history_and_sales_fields(self):
        self.client_obj.bonus_balance = Decimal("150.00")
        self.client_obj.save()
        r = self.quick(client=str(self.client_obj.id), bonus_redeemed="50.00",
                       payment={"method": "cash", "received": "150.00"})
        self.assertEqual(r.status_code, 201, r.data)
        cid = self.client_obj.id
        r = self.api.post(f"/api/main/clients/{cid}/bonus/",
                          {"delta": "30", "reason": "earn", "sale": r.data["id"]}, format="json")
        self.assertEqual(r.status_code, 201, r.data)
        self.assertTrue(r.data["transaction"]["branch"] is None or r.data["transaction"]["branch"])
        self.assertIn("cashbox", r.data["transaction"])
        redeem = T.objects.get(reason="redeem")
        self.assertEqual(str(redeem.cashbox_id), str(self.cashbox.id))

        s = self.api.get("/api/main/clients/bonus/summary/?by=branch")
        self.assertEqual(s.status_code, 200, s.content[:300])
        d = s.json()
        self.assertEqual((d["earned"], d["redeemed"], d["expired"]), ("30.00", "50.00", "0.00"))
        self.assertEqual(d["balance_total"], "130.00")
        self.assertEqual(d["clients_with_balance"], 1)
        self.assertEqual(d["active_clients"], 1)
        self.assertEqual(len(d["by_day"]), 1)
        self.assertIn("by_branch", d)
        self.assertIn("matrix", d)
        s2 = self.api.get("/api/main/clients/bonus/summary/?date_from=2000-01-01&date_to=2000-01-02").json()
        self.assertEqual(s2["earned"], "0.00")

        h = self.api.get(f"/api/main/clients/{cid}/bonus/history/?reason=redeem").json()
        self.assertEqual(len(h["results"]), 1)
        h = self.api.get(f"/api/main/clients/{cid}/bonus/history/?date_from=2000-01-01&date_to=2000-01-02").json()
        self.assertEqual(h["results"], [])
        self.assertEqual(self.api.get(f"/api/main/clients/{cid}/bonus/history/?reason=zzz").status_code, 400)

        rows = self.api.get("/api/main/pos/sales/").json()
        rows = rows["results"] if isinstance(rows, dict) else rows
        self.assertEqual(rows[0]["bonus_used"], "50.00")
        self.assertEqual(rows[0]["bonus_earned"], "30.00")
        self.assertIn("branch_name", rows[0])


class BonusUsedOnSaleTests(KassaBase):
    def test_redeem_by_separate_request_marks_sale(self):
        # ТЗ 31.10 п.13: чек без бонусов, потом касса списывает бонусы отдельным запросом с sale
        from apps.main.models import Sale
        self.client_obj.bonus_balance = Decimal("100.00")
        self.client_obj.save()
        r = self.quick(client=str(self.client_obj.id), payment={"method": "cash", "received": "200.00"})
        self.assertEqual(r.status_code, 201, r.data)
        sid = r.data["id"]
        total_before = Sale.objects.get(pk=sid).total
        b = self.api.post(f"/api/main/clients/{self.client_obj.id}/bonus/",
                          {"delta": "-25", "reason": "redeem", "sale": sid}, format="json", HTTP_IDEMPOTENCY_KEY="bk-1")
        self.assertEqual(b.status_code, 201, b.data)
        # повтор с тем же ключом не удваивает
        self.api.post(f"/api/main/clients/{self.client_obj.id}/bonus/",
                      {"delta": "-25", "reason": "redeem", "sale": sid}, format="json", HTTP_IDEMPOTENCY_KEY="bk-1")
        s = Sale.objects.get(pk=sid)
        self.assertEqual(s.bonus_redeemed, Decimal("25.00"))
        self.assertEqual(s.total, total_before)
