"""ТЗ кассы 05.11 п.17: replayed у перемещений, журнал ключей находит бонусы и перемещения."""
from decimal import Decimal

from apps.main.models import Client, ClientBonusTransaction
from apps.main.tests_branch_transfers import BranchTransferBodyIdempotencyTests


class Idem1105Tests(BranchTransferBodyIdempotencyTests):
    def test_transfer_replayed_and_lookup(self):
        a = self.client.post("/main/branch-transfers/", self._payload(idempotency_key="bt-r-1"), format="json")
        b = self.client.post("/main/branch-transfers/", self._payload(idempotency_key="bt-r-1"), format="json")
        self.assertEqual(a.status_code, 201, a.data)
        self.assertFalse(a.data["replayed"])
        self.assertTrue(b.data["replayed"])
        r = self.client.get("/main/idempotency/bt-r-1/")
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data["state"], "done")
        self.assertEqual(r.data["response"]["id"], a.data["id"])

    def test_bonus_lookup(self):
        cl = Client.objects.create(company=self.company, full_name="К", phone="+996700111222")
        ClientBonusTransaction.objects.create(company=self.company, client=cl, delta=Decimal("10"),
                                              balance_after=Decimal("10"), reason="manual", idempotency_key="bon-1")
        r = self.client.get("/main/idempotency/bon-1/")
        self.assertEqual(r.status_code, 200, getattr(r, "data", None))
        self.assertEqual(r.data["response"]["bonus_balance"], "10.00")
