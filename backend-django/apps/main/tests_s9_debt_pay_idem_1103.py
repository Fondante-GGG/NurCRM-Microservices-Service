"""S9 (аудит 03.11): POST main/debts/{id}/pay/ принимает Idempotency-Key / idempotency_key."""
from decimal import Decimal

from django.test import override_settings

from apps.construction.models import CashFlow
from apps.main.models import Debt, DebtPayment
from apps.users.tests_tz_n16_permissions import LOCMEM, N16Base


@override_settings(CACHES=LOCMEM)
class DebtPayIdempotencyTests(N16Base):
    def setUp(self):
        super().setUp()
        self.debt = Debt.objects.create(company=self.company, name="Долг Айбек", phone="+996555000333",
                                        amount=Decimal("1000.00"))
        self.url = f"/api/main/debts/{self.debt.id}/pay/"

    def flows(self):
        return CashFlow.objects.filter(source_kind=CashFlow.SourceKind.DEBT_REPAYMENT, source_id=str(self.debt.id)).count()

    def test_header_key_repeats_without_second_payment(self):
        body = {"amount": "100.00", "payment_method": "cash"}
        r1 = self.api_owner.post(self.url, body, format="json", HTTP_IDEMPOTENCY_KEY="pay-1")
        self.assertEqual(r1.status_code, 201, r1.content)
        r2 = self.api_owner.post(self.url, body, format="json", HTTP_IDEMPOTENCY_KEY="pay-1")
        self.assertEqual(r2.status_code, 201, r2.content)
        self.assertEqual(r1.json(), r2.json())
        self.assertEqual(DebtPayment.objects.filter(debt=self.debt).count(), 1)
        self.assertEqual(self.flows(), 1)

    def test_body_key(self):
        body = {"amount": "50.00", "payment_method": "cash", "idempotency_key": "pay-b"}
        self.assertEqual(self.api_owner.post(self.url, body, format="json").status_code, 201)
        self.assertEqual(self.api_owner.post(self.url, body, format="json").status_code, 201)
        self.assertEqual(DebtPayment.objects.filter(debt=self.debt).count(), 1)

    def test_same_key_other_body_conflict(self):
        self.api_owner.post(self.url, {"amount": "10.00"}, format="json", HTTP_IDEMPOTENCY_KEY="pay-c")
        r = self.api_owner.post(self.url, {"amount": "20.00"}, format="json", HTTP_IDEMPOTENCY_KEY="pay-c")
        self.assertEqual(r.status_code, 409, r.content)
        self.assertEqual(DebtPayment.objects.filter(debt=self.debt).count(), 1)

    def test_without_key_as_before(self):
        body = {"amount": "10.00"}
        self.assertEqual(self.api_owner.post(self.url, body, format="json").status_code, 201)
        self.assertEqual(self.api_owner.post(self.url, body, format="json").status_code, 201)
        self.assertEqual(DebtPayment.objects.filter(debt=self.debt).count(), 2)
