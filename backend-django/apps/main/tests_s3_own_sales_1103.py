"""S3 (аудит 03.11): кассир видит только свои чеки и возвраты на сервере; поиск по возвратам."""
import uuid
from decimal import Decimal

from django.test import override_settings

from apps.main.models import Sale, SaleItem, SaleReturn
from apps.users.models import User
from apps.users.tests_tz_n16_permissions import LOCMEM, N16Base


@override_settings(CACHES=LOCMEM)
class OwnSalesTests(N16Base):
    def setUp(self):
        super().setUp()
        self.colleague = User.objects.create_user(email=f"k{uuid.uuid4().hex[:6]}@t.kg", password="x",
                                                  company=self.company, role=None, can_view_sale=True)
        self.accountant = User.objects.create_user(email=f"b{uuid.uuid4().hex[:6]}@t.kg", password="x",
                                                   company=self.company, role=None, can_view_analytics=True)
        self.s_me = self.sale(self.cashier, 1)
        self.s_col = self.sale(self.colleague, 2, client=self.client_obj)
        self.s_own = self.sale(self.owner, 3)
        self.r_me = SaleReturn.objects.create(sale=self.s_col, company=self.company, user=self.cashier,
                                              idempotency_key="r1", returned_amount=Decimal("10"), reason="брак")
        self.r_col = SaleReturn.objects.create(sale=self.s_own, company=self.company, user=self.colleague,
                                               idempotency_key="r2", returned_amount=Decimal("20"))

    def sale(self, user, n, client=None):
        s = Sale.objects.create(company=self.company, user=user, status=Sale.Status.PAID, cashbox=self.cashbox,
                                total=Decimal("100"), doc_number=n, client=client)
        SaleItem.objects.create(company=self.company, sale=s, product=self.product, name_snapshot=f"Хлеб {n}",
                                unit_price=Decimal("100"), quantity=Decimal("1"))
        return s

    def ids(self, api, q=""):
        r = api.get("/api/main/pos/sales/" + q)
        self.assertEqual(r.status_code, 200, r.content)
        return {x["id"] for x in r.json()["results"]}

    def ret_ids(self, api, q=""):
        r = api.get("/api/main/pos/returns/" + q)
        self.assertEqual(r.status_code, 200, r.content)
        return {x["id"] for x in r.json()}

    def test_cashier_sees_only_own_sales(self):
        self.assertEqual(self.ids(self.api_cashier), {str(self.s_me.id)})
        # чужой user= не помогает
        self.assertEqual(self.ids(self.api_cashier, f"?user={self.colleague.id}"), set())
        self.assertEqual(self.ids(self.api_cashier, f"?cashier={self.owner.id}"), set())

    def test_exact_number_and_client_lookup_still_work(self):
        # возврат по чеку коллеги на кассе и долги клиента — как раньше
        self.assertEqual(self.ids(self.api_cashier, "?number=2"), {str(self.s_col.id)})
        self.assertEqual(self.ids(self.api_cashier, f"?client={self.client_obj.id}"), {str(self.s_col.id)})
        r = self.api_cashier.get(f"/api/main/pos/sales/{self.s_col.id}/")
        self.assertEqual(r.status_code, 200, r.content)
        # чеки смены (касса NurMarket, «История чеков») — все чеки этой смены
        shift = self.open_shift(self.colleague)
        Sale.objects.filter(pk=self.s_col.pk).update(shift=shift)
        self.assertEqual(self.ids(self.api_cashier, f"?shift={shift.id}"), {str(self.s_col.id)})

    def test_owner_admin_accountant_see_all(self):
        everything = {str(self.s_me.id), str(self.s_col.id), str(self.s_own.id)}
        self.assertEqual(self.ids(self.api_owner), everything)
        self.assertEqual(self.ids(self.api_admin), everything)
        self.assertEqual(self.ids(self.api_for(self.accountant)), everything)
        self.assertEqual(self.ids(self.api_owner, f"?user={self.cashier.id}"), {str(self.s_me.id)})

    def test_returns_own_only_but_sale_filter_open(self):
        self.assertEqual(self.ret_ids(self.api_cashier), {str(self.r_me.id)})
        # возвраты по чеку (касса проверяет, что уже вернули) — видны
        self.assertEqual(self.ret_ids(self.api_cashier, f"?sale={self.s_own.id}"), {str(self.r_col.id)})
        self.assertEqual(self.ret_ids(self.api_owner), {str(self.r_me.id), str(self.r_col.id)})

    def test_returns_search(self):
        self.assertEqual(self.ret_ids(self.api_owner, "?search=2"), {str(self.r_me.id)})  # номер чека 2
        self.assertEqual(self.ret_ids(self.api_owner, "?search=брак"), {str(self.r_me.id)})
        self.assertEqual(self.ret_ids(self.api_owner, "?search=Айбек"), {str(self.r_me.id)})
        self.assertEqual(self.ret_ids(self.api_owner, "?search=Хлеб 3"), {str(self.r_col.id)})
        r = self.api_owner.get("/api/main/pos/returns/?search=Хлеб&page=1&page_size=1")
        self.assertEqual(r.json()["count"], 2)
