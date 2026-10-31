"""ТЗ 31.10 п.13: у чека должен быть branch (из смены, кассы или кассира)."""
from decimal import Decimal

from django.core.management import call_command

from apps.construction.models import CashShift
from apps.main.models import Branch, Sale
from apps.main.tests_kassa_api import KassaBase


class SaleBranchTests(KassaBase):
    def _sale(self, r):
        self.assertEqual(r.status_code, 201, r.data)
        sid = r.data.get("sale_id") or r.data.get("id")
        return Sale.objects.get(pk=sid)

    def test_branch_from_cashbox_when_shift_has_none(self):
        br = Branch.objects.create(company=self.company, name="Филиал 1")
        self.cashbox.branch = br
        self.cashbox.save()
        CashShift.objects.filter(pk=self.shift.pk).update(branch=None)
        sale = self._sale(self.quick(payment={"method": "cash", "received": "200.00"}))
        self.assertEqual(sale.branch_id, br.id)

    def test_branch_from_shift(self):
        br = Branch.objects.create(company=self.company, name="Филиал 2")
        CashShift.objects.filter(pk=self.shift.pk).update(branch=br)
        sale = self._sale(self.quick(payment={"method": "cash", "received": "200.00"}))
        self.assertEqual(sale.branch_id, br.id)

    def test_backfill_command_dry_run_and_apply(self):
        br = Branch.objects.create(company=self.company, name="Филиал 3")
        self.cashbox.branch = br
        self.cashbox.save()
        sale = self._sale(self.quick(payment={"method": "cash", "received": "200.00"}))
        Sale.objects.filter(pk=sale.pk).update(branch=None)
        call_command("backfill_sale_branch")
        sale.refresh_from_db()
        self.assertIsNone(sale.branch_id)
        call_command("backfill_sale_branch", "--apply")
        sale.refresh_from_db()
        self.assertEqual(sale.branch_id, br.id)
