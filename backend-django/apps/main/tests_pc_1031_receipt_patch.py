"""
ТЗ редактор накладных 30.10 (вариант А): PATCH suppliers/receipts/{id}/ — правка прихода.
Коды ошибок, построчные возвраты, dry_run, Idempotency-Key, версии и откат, деньги, дробное у весовых,
право и окно правки — только владелец. (Было: ТЗ 31.10 п.21.)
"""
from datetime import timedelta
from decimal import Decimal
import uuid

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.construction.models import Cashbox, CashFlow, CashShift
from apps.main.models import (
    ChangeEvent, Client, ClientDeal, DealInstallment, Product, StockMovement, SupplierReceipt, SupplierReceiptItem,
    SupplierReceiptVersion,
)
from apps.users.models import Company, CompanyAppSettings, SubscriptionPlan

User = get_user_model()
REASON = "Опечатка в количестве"


class ReceiptEditBase(TestCase):
    def setUp(self):
        self.api = APIClient()
        self.owner = User.objects.create_user(email=f"o_{uuid.uuid4().hex[:6]}@t.com", password="pass", role="owner",
                                              first_name="Умар")
        plan = SubscriptionPlan.objects.create(name="Pro", price=Decimal("100.00"))
        self.company = Company.objects.create(name="Co", owner=self.owner, subscription_plan=plan)
        self.owner.company = self.company
        self.owner.save()
        self.api.force_authenticate(user=self.owner)
        self.sup = Client.objects.create(full_name="Альфа", type=Client.StatusClient.SUPPLIERS, company=self.company)
        self.p = Product.objects.create(name="Печенье", company=self.company, quantity=Decimal("0"),
                                        purchase_price=Decimal("10.00"), price=Decimal("15.00"))
        self.p2 = Product.objects.create(name="Чай", company=self.company, quantity=Decimal("0"),
                                         purchase_price=Decimal("5.00"), price=Decimal("8.00"))
        self.pw = Product.objects.create(name="Сыр", company=self.company, quantity=Decimal("0"), unit="кг",
                                         is_weight=True, purchase_price=Decimal("300.00"), price=Decimal("400.00"))
        r = self.receive([{"product": str(self.p.id), "qty": 10, "purchase_price": "10.00"}])
        self.rid = r.data["id"]
        self.deal = ClientDeal.objects.get(pk=r.data["deal_id"])
        self.item = SupplierReceiptItem.objects.get(receipt_id=self.rid)
        self.url = f"/api/main/suppliers/receipts/{self.rid}/"

    def receive(self, items, **extra):
        body = {"create_deal": True, "payment_type": "debt", "items": items, **extra}
        r = self.api.post(f"/api/main/suppliers/{self.sup.id}/receipt/", body, format="json")
        self.assertEqual(r.status_code, 200, r.data)
        return r

    def patch(self, body, api=None, key=True, url=None, **headers):
        body = {"reason": REASON, **body}
        if key:
            headers.setdefault("HTTP_IDEMPOTENCY_KEY", str(uuid.uuid4()))
        return (api or self.api).patch(url or self.url, body, format="json", **headers)

    def user(self, role="salesperson", **perms):
        u = User.objects.create_user(email=f"e_{uuid.uuid4().hex[:6]}@t.com", password="pass",
                                     role=role, company=self.company, **perms)
        api = APIClient()
        api.force_authenticate(user=u)
        return u, api

    def code(self, r, http):
        self.assertEqual(r.status_code, http, r.data)
        return r.data["code"]


class ReceiptPatchTests(ReceiptEditBase):
    # --- чтение ---
    def test_get_has_edit_fields(self):
        r = self.api.get(self.url)
        d = r.data
        self.assertEqual((d["version"], r["ETag"], d["edited"], d["edit_count"]), (1, '"1"', False, 0))
        self.assertTrue(d["can_edit"])
        self.assertIsNone(d["edit_block_reason"])
        self.assertEqual(d["edit_window"], "24h")
        self.assertIsNotNone(d["edit_window_until"])
        self.assertEqual((d["payment_type"], d["debt_amount"], d["deal_id"]), ("debt", "100.00", str(self.deal.id)))
        self.assertEqual(d["lines"][0]["qty"], 10)  # целое — числом, как раньше
        self.assertEqual(d["lines"][0]["returned_qty"], "0")
        lst = self.api.get("/api/main/suppliers/receipts/").data["results"][0]
        self.assertIn("can_edit", lst)
        _, admin = self.user(role="admin")
        d = admin.get(self.url).data
        self.assertEqual((d["can_edit"], d["edit_block_reason"]), (False, "permission_denied"))

    # --- успешная правка ---
    def test_change_qty_and_price(self):
        r = self.patch({"lines": [{"id": str(self.item.id), "qty": "8.000", "purchase_price": "12.5"}],
                        "reason_code": "qty_typo", "document_number": "Н-77", "comment": "исправили",
                        "device": "Касса-1", "source": "kassa"}, HTTP_IF_MATCH='"1"')
        self.assertEqual(r.status_code, 200, r.data)
        rc, dl = r.data["receipt"], r.data["deltas"]
        self.assertEqual((rc["version"], rc["edited"], rc["edit_count"]), (2, True, 1))
        self.assertEqual(rc["edited_by"]["id"], str(self.owner.id))
        self.assertEqual((rc["document_number"], rc["comment"], rc["total_amount"]), ("Н-77", "исправили", "100.00"))
        self.assertEqual(r["ETag"], '"2"')
        self.assertFalse(r.data["replayed"])
        self.assertEqual(dl["total"], {"before": "100.00", "after": "100.00", "delta": "0.00"})
        self.assertEqual(dl["stock"][0]["qty_delta"], "-2.000")
        self.assertEqual((dl["purchase_price"][0]["after"], dl["purchase_price"][0]["applied"]), ("12.5000", True))
        self.assertEqual(len(r.data["movements"]), 1)
        mv = StockMovement.objects.get(pk=r.data["movements"][0])
        self.assertEqual((mv.type, mv.change, mv.ref_type, mv.ref_id), ("receipt_correction", Decimal("-2"),
                                                                       "receipt_correction", self.item.receipt_id))
        self.p.refresh_from_db()
        self.assertEqual((self.p.quantity, self.p.purchase_price), (Decimal("8"), Decimal("12.5")))
        self.deal.refresh_from_db()
        self.assertEqual(self.deal.amount, Decimal("100.00"))

    def test_qty_down_reduces_debt(self):
        r = self.patch({"lines": [{"id": str(self.item.id), "qty": 8}]})
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data["deltas"]["supplier_debt"],
                         {"deal_id": str(self.deal.id), "before": "100.00", "after": "80.00", "delta": "-20.00"})
        self.deal.refresh_from_db()
        self.assertEqual((self.deal.amount, self.deal.remaining_debt), (Decimal("80.00"), Decimal("80.00")))

    def test_items_alias_add_and_delete(self):
        r = self.patch({"items": [{"product": str(self.p2.id), "qty": 4, "line_total": "21.00",
                                   "client_row_id": "row-1"}]})
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data["receipt"]["total_amount"], "121.00")
        self.assertEqual(r.data["deltas"]["lines"][0]["client_row_id"], "row-1")
        self.p2.refresh_from_db()
        self.assertEqual((self.p2.quantity, self.p2.purchase_price), (Decimal("4"), Decimal("5.25")))
        r = self.patch({"lines": [{"id": str(self.item.id), "delete": True}]})
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data["receipt"]["total_amount"], "21.00")
        self.p.refresh_from_db()
        self.assertEqual(self.p.quantity, Decimal("0"))

    def test_delete_last_receipt_line_reverts_purchase_price(self):
        SupplierReceipt.objects.filter(pk=self.rid).update(created_at=timezone.now() - timedelta(hours=2))
        r2 = self.receive([{"product": str(self.p.id), "qty": 2, "purchase_price": "11.00"},
                           {"product": str(self.p2.id), "qty": 1, "purchase_price": "5.00"}])
        self.p.refresh_from_db()
        self.assertEqual(self.p.purchase_price, Decimal("11.00"))
        line = SupplierReceiptItem.objects.get(receipt_id=r2.data["id"], product=self.p)
        r = self.patch({"lines": [{"id": str(line.id), "delete": True}]},
                       url=f"/api/main/suppliers/receipts/{r2.data['id']}/")
        self.assertEqual(r.status_code, 200, r.data)
        self.p.refresh_from_db()
        self.assertEqual(self.p.purchase_price, Decimal("10.00"))  # откат к прошлому приходу

    def test_price_not_applied_if_not_latest_and_rules(self):
        SupplierReceipt.objects.filter(pk=self.rid).update(created_at=timezone.now() - timedelta(hours=2))
        self.receive([{"product": str(self.p.id), "qty": 1, "purchase_price": "11.00"}])
        r = self.patch({"lines": [{"id": str(self.item.id), "purchase_price": "9"}]})
        self.assertEqual(r.status_code, 200, r.data)
        pp = r.data["deltas"]["purchase_price"][0]
        self.assertEqual((pp["applied"], pp["after"], pp["proposed"]), (False, "11.0000", "9.0000"))
        self.p.refresh_from_db()
        self.assertEqual(self.p.purchase_price, Decimal("11.00"))
        r = self.patch({"lines": [{"id": str(self.item.id), "purchase_price": "8"}],
                        "update_product_purchase_price": "always"})
        self.assertTrue(r.data["deltas"]["purchase_price"][0]["applied"])
        self.p.refresh_from_db()
        self.assertEqual(self.p.purchase_price, Decimal("8"))

    def test_cannot_delete_last_line(self):
        r = self.patch({"lines": [{"id": str(self.item.id), "delete": True}]})
        self.assertEqual(self.code(r, 422), "validation_error")

    def test_dry_run_writes_nothing_and_needs_no_key(self):
        r = self.patch({"dry_run": True, "lines": [{"id": str(self.item.id), "qty": 5}]}, key=False)
        self.assertEqual(r.status_code, 200, r.data)
        self.assertTrue(r.data["dry_run"])
        self.assertEqual(r.data["receipt"]["version"], 1)
        self.assertEqual(r.data["deltas"]["total"]["after"], "50.00")
        self.assertEqual(r.data["deltas"]["supplier_debt"]["after"], "50.00")
        self.assertEqual(r.data["movements"], [])
        self.p.refresh_from_db(); self.item.refresh_from_db(); self.deal.refresh_from_db()
        self.assertEqual((self.p.quantity, self.item.qty, self.deal.amount), (Decimal("10"), 10, Decimal("100.00")))
        self.assertFalse(SupplierReceiptVersion.objects.exists())
        # ключ dry_run не занимается: тот же ключ потом проводит правку
        key = str(uuid.uuid4())
        self.api.patch(self.url + "?dry_run=1", {"lines": [{"id": str(self.item.id), "qty": 5}]}, format="json",
                       HTTP_IDEMPOTENCY_KEY=key)
        r = self.patch({"lines": [{"id": str(self.item.id), "qty": 5}]}, HTTP_IDEMPOTENCY_KEY=key)
        self.assertEqual((r.status_code, r.data["replayed"], r.data["receipt"]["version"]), (200, False, 2))

    def test_idempotency(self):
        r = self.patch({"lines": [{"id": str(self.item.id), "qty": 9}]}, key=False)
        self.assertEqual(self.code(r, 400), "idempotency_key_required")
        key = str(uuid.uuid4())
        body = {"lines": [{"id": str(self.item.id), "qty": 9}]}
        r1 = self.patch(body, HTTP_IDEMPOTENCY_KEY=key)
        r2 = self.patch(body, HTTP_IDEMPOTENCY_KEY=key)
        self.assertEqual((r1.status_code, r2.status_code), (200, 200))
        self.assertTrue(r2.data["replayed"])
        self.assertEqual(r2.data["receipt"]["version"], 2)
        self.p.refresh_from_db()
        self.assertEqual(self.p.quantity, Decimal("9"))  # не задвоилось
        r3 = self.patch({"lines": [{"id": str(self.item.id), "qty": 7}]}, HTTP_IDEMPOTENCY_KEY=key)
        self.assertEqual(self.code(r3, 409), "idempotency_conflict")

    def test_audit_log_written(self):
        from apps.construction.models import AuditLog

        self.patch({"lines": [{"id": str(self.item.id), "qty": 9}], "device": "ПК-1"})
        a = AuditLog.objects.get(object_type="supplier_receipt", object_id=str(self.rid))
        self.assertEqual(a.action, "edit")
        self.assertEqual((a.after["reason"], a.after["device"]), (REASON, "ПК-1"))
        self.assertTrue(a.after["diff"]["lines"])

    def test_receipt_changed_event_and_feed(self):
        with self.captureOnCommitCallbacks(execute=True):
            r = self.patch({"lines": [{"id": str(self.item.id), "qty": 9}]})
        self.assertEqual(r.status_code, 200, r.data)
        ev = ChangeEvent.objects.filter(company=self.company, type="receipt_changed").get()
        self.assertEqual((ev.data["receipt_id"], ev.data["version"]), (str(self.rid), 2))
        self.assertTrue(ChangeEvent.objects.filter(company=self.company, type="stock_changed").exists())
        from apps.main.events_stream import to_stream_event
        from apps.main.change_feed import serialize_event

        msg = to_stream_event(serialize_event(ev))
        self.assertEqual((msg["type"], msg["version"]), ("receipt_changed", 2))
        feed = self.api.get("/api/main/suppliers/receipts/changes/").data
        self.assertEqual([(c["receipt_id"], c["version"]) for c in feed["changes"]], [(str(self.rid), 2)])
        later = (timezone.now() + timedelta(minutes=5)).isoformat()
        self.assertEqual(self.api.get("/api/main/suppliers/receipts/changes/", {"since": later}).data["changes"], [])
        # товар попал в products/changes (updated_at)
        self.p.refresh_from_db()
        self.assertGreaterEqual(self.p.updated_at, SupplierReceipt.objects.get(pk=self.rid).edited_at - timedelta(seconds=1))

    def test_capability_flags(self):
        from core.capabilities import FEATURES

        self.assertIn("receipt_patch", FEATURES)
        self.assertIn("receipt_edit", FEATURES)


class ReceiptPatchErrorTests(ReceiptEditBase):
    def test_reason_required(self):
        r = self.api.patch(self.url, {"lines": [{"id": str(self.item.id), "qty": 9}]}, format="json",
                           HTTP_IDEMPOTENCY_KEY=str(uuid.uuid4()))
        self.assertEqual(self.code(r, 400), "reason_required")
        self.assertEqual(self.code(self.patch({"reason": "абв"}), 400), "reason_required")
        self.assertEqual(self.code(self.patch({"reason_code": "bad"}), 422), "validation_error")

    def test_version_conflict(self):
        self.patch({"comment": "a"})
        r = self.patch({"comment": "b"}, HTTP_IF_MATCH='"1"')
        self.assertEqual(self.code(r, 412), "version_conflict")
        self.assertEqual(r.data["data"]["current_version"], 2)
        self.assertEqual(r.data["data"]["edited_by"]["id"], str(self.owner.id))
        self.assertIsNotNone(r.data["data"]["edited_at"])
        r = self.patch({"comment": "b", "version": 1})
        self.assertEqual(self.code(r, 409), "version_conflict")
        self.assertEqual(self.patch({"comment": "b", "version": 2}).status_code, 200)

    def test_negative_stock(self):
        Product.objects.filter(pk=self.p.pk).update(quantity=Decimal("3"))  # 7 из 10 уже продали
        r = self.patch({"lines": [{"id": str(self.item.id), "qty": 6}]})
        self.assertEqual(self.code(r, 409), "negative_stock")
        it = r.data["data"]["items"][0]
        self.assertEqual((it["product_id"], it["stock_now"], it["qty_delta"], it["min_qty"]),
                         (str(self.p.id), "3.000", "-4.000", "7.000"))
        self.assertEqual(self.patch({"lines": [{"id": str(self.item.id), "qty": 7}]}).status_code, 200)
        self.p.refresh_from_db()
        self.assertEqual(self.p.quantity, Decimal("0"))

    def test_debt_already_paid(self):
        DealInstallment.objects.filter(deal=self.deal).update(paid_amount=Decimal("80.00"))
        r = self.patch({"lines": [{"id": str(self.item.id), "qty": 5}]})
        self.assertEqual(self.code(r, 409), "debt_already_paid")
        self.assertEqual(r.data["data"]["deal_id"], str(self.deal.id))
        self.assertEqual((r.data["data"]["paid"], r.data["data"]["new_total"]), ("80.00", "50.00"))
        self.deal.refresh_from_db()
        self.assertEqual(self.deal.amount, Decimal("100.00"))

    def test_debt_partly_paid_reduced_above_paid(self):
        DealInstallment.objects.filter(deal=self.deal).update(paid_amount=Decimal("30.00"))
        r = self.patch({"lines": [{"id": str(self.item.id), "qty": 6}]})
        self.assertEqual(r.status_code, 200, r.data)
        self.deal.refresh_from_db()
        self.assertEqual((self.deal.amount, self.deal.remaining_debt), (Decimal("60.00"), Decimal("30.00")))

    def _return(self, qty, item=None):
        item = item or self.item
        r = self.api.post(f"/api/main/suppliers/{self.sup.id}/returns/", {
            "receipt_id": self.rid, "reason": "defect", "compensation": "none",
            "items": [{"product_id": str(item.product_id), "qty": qty, "receipt_item_id": str(item.id)}]},
            format="json")
        self.assertEqual(r.status_code, 201, r.data)

    def test_has_returns_per_line(self):
        r = self.patch({"lines": [{"product": str(self.p2.id), "qty": 2, "purchase_price": "5"}]})
        line2 = SupplierReceiptItem.objects.get(receipt_id=self.rid, product=self.p2)
        self._return(2)
        lid = str(self.item.id)
        for bad in ({"id": lid, "purchase_price": "11"}, {"id": lid, "qty": 1}, {"id": lid, "delete": True}):
            r = self.patch({"lines": [bad]})
            self.assertEqual(self.code(r, 409), "has_returns")
            self.assertEqual(r.data["data"]["lines"], [{"id": lid, "returned_qty": "2.000"}])
        self.assertEqual(self.patch({"lines": [{"id": lid, "qty": 9}]}).status_code, 200)  # не ниже возвращённого
        self.assertEqual(self.patch({"lines": [{"id": str(line2.id), "purchase_price": "6"}]}).status_code, 200)
        self.assertEqual(self.patch({"document_number": "1"}).status_code, 200)  # шапку можно
        other = Client.objects.create(full_name="Бета", type=Client.StatusClient.SUPPLIERS, company=self.company)
        self.assertEqual(self.code(self.patch({"supplier_id": str(other.id)}), 409), "has_returns")

    def test_receipt_fully_returned(self):
        self._return(10)
        self.assertEqual(self.code(self.patch({"comment": "x"}), 409), "receipt_fully_returned")
        self.assertEqual(self.api.get(self.url).data["edit_block_reason"], "receipt_fully_returned")

    def test_period_closed_423(self):
        from apps.warehouse.models import WarehouseAccountingSettings

        WarehouseAccountingSettings.objects.create(company=self.company, closed_until=timezone.localdate())
        _, emp = self.user(can_edit_purchase_documents=True)
        r = self.patch({"comment": "x"}, api=emp)
        self.assertEqual(self.code(r, 423), "period_closed")
        self.assertEqual(r.data["data"]["closed_until"], timezone.localdate().isoformat())

    def test_edit_window(self):
        SupplierReceipt.objects.filter(pk=self.rid).update(created_at=timezone.now() - timedelta(hours=25))
        r = self.patch({"comment": "x"})
        self.assertEqual(self.code(r, 409), "edit_window_expired")
        self.assertEqual(r.data["data"]["window"], "24h")
        self.assertTrue(r.data["data"]["created_at"] and r.data["data"]["expired_at"])
        self.assertEqual(self.api.get(self.url).data["edit_block_reason"], "edit_window_expired")
        # запасное значение — вчерашняя настройка в app-settings кассы
        CompanyAppSettings.objects.create(company=self.company, app="nurmarket-mobile",
                                          settings={"receipt_edit_window": "48h"})
        self.assertEqual(self.patch({"comment": "x"}).status_code, 200)
        # настройка компании важнее
        Company.objects.filter(pk=self.company.pk).update(receipt_edit_window="24h")
        self.assertEqual(self.code(self.patch({"comment": "y"}), 409), "edit_window_expired")
        Company.objects.filter(pk=self.company.pk).update(receipt_edit_window="always")
        SupplierReceipt.objects.filter(pk=self.rid).update(created_at=timezone.now() - timedelta(days=20))
        self.assertEqual(self.patch({"comment": "z"}).status_code, 200)

    def test_validation_and_fractional(self):
        r = self.patch({"lines": [{"id": str(self.item.id), "qty": 0}]})
        self.assertEqual(self.code(r, 422), "validation_error")
        self.assertIn("lines[0].qty", r.data["data"]["fields"])
        self.assertEqual(self.code(self.patch({"lines": [{"id": str(self.item.id), "purchase_price": "0"}]}), 422),
                         "validation_error")
        self.assertEqual(self.code(self.patch({"lines": [{"id": str(uuid.uuid4()), "qty": 1}]}), 422),
                         "validation_error")
        r = self.patch({"lines": [{"id": str(self.item.id), "qty": "9.5"}]})
        self.assertEqual(self.code(r, 422), "fractional_not_allowed")


class ReceiptWeightAndMoneyTests(ReceiptEditBase):
    def test_fractional_weight_receipt(self):
        r = self.api.post(f"/api/main/suppliers/{self.sup.id}/receipt/", {
            "items": [{"product": str(self.p.id), "qty": "1.5", "purchase_price": "10"}]}, format="json")
        self.assertEqual(self.code(r, 400), "fractional_not_allowed")
        r = self.receive([{"product": str(self.pw.id), "qty": "2.5", "purchase_price": "300"}])
        self.pw.refresh_from_db()
        self.assertEqual(self.pw.quantity, Decimal("2.5"))
        line = SupplierReceiptItem.objects.get(receipt_id=r.data["id"])
        self.assertEqual(line.qty, Decimal("2.500"))
        self.assertEqual(r.data["total_amount"], "750.00")
        url = f"/api/main/suppliers/receipts/{r.data['id']}/"
        self.assertEqual(self.api.get(url).data["lines"][0]["qty"], 2.5)
        r = self.patch({"lines": [{"id": str(line.id), "qty": "1.250"}]}, url=url)
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data["deltas"]["stock"][0]["qty_delta"], "-1.250")
        self.assertEqual(r.data["deltas"]["total"]["after"], "375.00")
        self.pw.refresh_from_db()
        self.assertEqual(self.pw.quantity, Decimal("1.25"))

    def _cash_receipt(self, shift=None):
        self.cashbox = Cashbox.objects.create(name="Касса 1", company=self.company)
        extra = {"shift": str(shift.id)} if shift else {"cashbox_id": str(self.cashbox.id)}
        r = self.api.post(f"/api/main/suppliers/{self.sup.id}/receipt/", {
            "items": [{"product": str(self.p2.id), "qty": 5, "purchase_price": "100"}], "payment_type": "cash",
            **extra}, format="json")
        self.assertEqual(r.status_code, 200, r.data)
        return r.data["id"], SupplierReceiptItem.objects.get(receipt_id=r.data["id"])

    def test_cash_paid_receipt_posts_difference(self):
        rid, line = self._cash_receipt()
        url = f"/api/main/suppliers/receipts/{rid}/"
        r = self.patch({"lines": [{"id": str(line.id), "purchase_price": "90"}]}, url=url)
        self.assertEqual(r.status_code, 200, r.data)
        cf = r.data["deltas"]["cashflows"]
        self.assertEqual((len(cf), cf[0]["type"], cf[0]["amount"], cf[0]["cashbox"]),
                         (1, "income", "50.00", str(self.cashbox.id)))
        self.assertTrue(CashFlow.objects.filter(pk=cf[0]["id"], type="income", amount=Decimal("50.00"),
                                                source_id=rid).exists())
        self.assertEqual(self.api.get(url).data["paid_amount"], "450.00")
        r = self.patch({"lines": [{"id": str(line.id), "qty": 6}]}, url=url)  # доплата 90
        cf = r.data["deltas"]["cashflows"]
        self.assertEqual((cf[0]["type"], cf[0]["amount"]), ("expense", "90.00"))

    def test_closed_shift_money_to_main_cashbox(self):
        cb = Cashbox.objects.create(name="Ящик", company=self.company)
        shift = CashShift.objects.create(company=self.company, cashbox=cb, cashier=self.owner,
                                         status=CashShift.Status.OPEN)
        rid, line = self._cash_receipt(shift=shift)
        CashShift.objects.filter(pk=shift.pk).update(status=CashShift.Status.CLOSED)
        r = self.patch({"lines": [{"id": str(line.id), "qty": 4}]}, url=f"/api/main/suppliers/receipts/{rid}/")
        self.assertEqual(r.status_code, 200, r.data)
        self.assertIn({"code": "shift_closed_money_to_main"}, r.data["warnings"])
        cf = CashFlow.objects.get(pk=r.data["deltas"]["cashflows"][0]["id"])
        self.assertIsNone(cf.shift_id)
        self.assertEqual((cf.type, cf.amount), ("income", Decimal("100.00")))

    def test_payment_change_debt_to_cash(self):
        cb = Cashbox.objects.create(name="Касса 1", company=self.company)
        r = self.patch({"payment": {"type": "cash", "cashbox_id": str(cb.id)}})
        self.assertEqual(r.status_code, 200, r.data)
        self.assertFalse(ClientDeal.objects.filter(pk=self.deal.pk).exists())
        self.assertTrue(CashFlow.objects.filter(source_id=self.rid, type="expense", amount=Decimal("100.00"),
                                                cashbox=cb).exists())
        self.assertEqual(self.api.get(self.url).data["payment_type"], "cash")
        r = self.patch({"payment": {"type": "debt", "due_date": "2026-12-01"}})
        self.assertEqual(r.status_code, 200, r.data)
        self.assertTrue(CashFlow.objects.filter(source_id=self.rid, type="income", amount=Decimal("100.00")).exists())
        d = self.api.get(self.url).data
        self.assertEqual((d["payment_type"], d["debt_amount"]), ("debt", "100.00"))

    def test_supplier_change_moves_deal(self):
        other = Client.objects.create(full_name="Бета", type=Client.StatusClient.SUPPLIERS, company=self.company)
        r = self.patch({"supplier_id": str(other.id)})
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data["receipt"]["supplier_id"], str(other.id))
        self.deal.refresh_from_db()
        self.assertEqual(self.deal.client_id, other.id)
        self.assertEqual(self.api.get(self.url).data["deal_id"], str(self.deal.id))
        DealInstallment.objects.filter(deal=self.deal).update(paid_amount=Decimal("10.00"))
        r = self.patch({"supplier_id": str(self.sup.id)})
        self.assertEqual(self.code(r, 409), "debt_already_paid")


class ReceiptVersionsTests(ReceiptEditBase):
    def test_versions_and_revert(self):
        self.assertEqual(len(self.api.get(self.url + "versions/").data["results"]), 1)  # ещё не правили
        self.patch({"lines": [{"id": str(self.item.id), "qty": 8}], "reason": "Пересчитали коробки"})
        self.patch({"lines": [{"id": str(self.item.id), "purchase_price": "12"}], "reason": "Цена по счёту",
                    "reason_code": "price_typo"})
        vs = self.api.get(self.url + "versions/").data
        self.assertEqual(vs["current_version"], 3)
        self.assertEqual([v["version"] for v in vs["results"]], [1, 2, 3])
        self.assertEqual((vs["results"][2]["reason"], vs["results"][2]["total"], vs["results"][2]["total_before"]),
                         ("Цена по счёту", "96.00", "80.00"))
        self.assertEqual(vs["results"][1]["lines_diff"][0]["qty_after"], "8.000")
        v1 = self.api.get(self.url + "versions/1/").data
        self.assertEqual(v1["snapshot"]["lines"][0]["qty"], "10.000")
        self.assertEqual(self.api.get(self.url + "versions/9/").status_code, 404)
        # откат: новая версия 4 с составом версии 1
        r = self.api.post(self.url + "revert/", {"to_version": 1}, format="json", HTTP_IDEMPOTENCY_KEY=str(uuid.uuid4()))
        self.assertEqual(self.code(r, 400), "reason_required")
        r = self.api.post(self.url + "revert/", {"to_version": 1, "reason": "Вернуть как было"}, format="json")
        self.assertEqual(self.code(r, 400), "idempotency_key_required")
        r = self.api.post(self.url + "revert/", {"to_version": 1, "reason": "Вернуть как было", "version": 3},
                          format="json", HTTP_IDEMPOTENCY_KEY=str(uuid.uuid4()))
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data["receipt"]["version"], 4)
        self.assertEqual(r.data["deltas"]["total"], {"before": "96.00", "after": "100.00", "delta": "4.00"})
        self.assertEqual(r.data["deltas"]["stock"][0]["qty_delta"], "2.000")
        self.item.refresh_from_db(); self.p.refresh_from_db(); self.deal.refresh_from_db()
        self.assertEqual((self.item.qty, self.item.purchase_price), (Decimal("10"), Decimal("10.00")))
        self.assertEqual((self.p.quantity, self.p.purchase_price, self.deal.amount),
                         (Decimal("10"), Decimal("10.00"), Decimal("100.00")))
        vs = self.api.get(self.url + "versions/").data["results"]
        self.assertEqual((vs[-1]["version"], vs[-1]["action"]), (4, "revert"))


class ReceiptEditAccessTests(ReceiptEditBase):
    def test_only_owner_by_default(self):
        _, admin = self.user(role="admin")
        r = self.patch({"comment": "x"}, api=admin)
        self.assertEqual(self.code(r, 403), "permission_denied")
        self.assertEqual(r.data["data"]["required"], "can_edit_purchase_documents")
        _, emp = self.user()
        self.assertEqual(self.code(self.patch({"comment": "x"}, api=emp), 403), "permission_denied")
        _, granted = self.user(can_edit_purchase_documents=True)
        self.assertEqual(self.patch({"comment": "x"}, api=granted).status_code, 200)

    def test_right_granted_only_by_owner(self):
        target, _ = self.user()
        _, admin = self.user(role="admin")
        url = f"/api/users/employees/{target.id}/"
        r = admin.patch(url, {"can_edit_purchase_documents": True}, format="json")
        self.assertEqual(r.status_code, 400, r.data)
        r = self.api.patch(url, {"can_edit_purchase_documents": True}, format="json")
        self.assertEqual(r.status_code, 200, r.data)
        self.assertTrue(r.data["can_edit_purchase_documents"])
        rows = {str(u["id"]): u for u in self.api.get("/api/users/employees/").data.get("results", [])} or {
            str(u["id"]): u for u in self.api.get("/api/users/employees/").data}
        self.assertTrue(rows[str(target.id)]["can_edit_purchase_documents"])
        self.assertTrue(self.api.get("/api/users/profile/").data["can_edit_purchase_documents"])  # владелец
        self.assertFalse(admin.get("/api/users/profile/").data["can_edit_purchase_documents"])
        # сам себе выдать нельзя
        _, emp = self.user()
        self.assertEqual(emp.patch("/api/users/profile/", {"can_edit_purchase_documents": True},
                                   format="json").status_code, 400)

    def test_window_changed_only_by_owner(self):
        _, admin = self.user(role="admin")
        self.assertEqual(self.api.get("/api/users/company/").data["receipt_edit_window"], "24h")
        r = admin.patch("/api/users/company/", {"receipt_edit_window": "48h"}, format="json")
        self.assertIn(r.status_code, (403,), r.data)
        r = admin.patch("/api/users/settings/company/", {"receipt_edit_window": "48h"}, format="json")
        self.assertEqual(self.code(r, 403), "permission_denied")
        r = self.api.patch("/api/users/company/", {"receipt_edit_window": "always"}, format="json")
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data["receipt_edit_window"], "always")
        self.assertTrue(r.data["receipt_edit_window_editable"])
        self.assertEqual(self.code(self.api.patch("/api/users/company/", {"receipt_edit_window": "12h"},
                                                  format="json"), 400), "validation_error")
        self.assertFalse(admin.get("/api/users/company/").data["receipt_edit_window_editable"])


class ReceiptHistoryAliasTests(ReceiptEditBase):
    def test_history_is_alias_of_versions(self):
        self.assertEqual(self.patch({"lines": [{"id": str(self.item.id), "qty": 9}]}).status_code, 200)
        a = self.api.get(self.url + "versions/")
        b = self.api.get(self.url + "history/")
        self.assertEqual(b.status_code, 200, b.data)
        self.assertEqual(a.data, b.data)
        self.assertEqual([r["version"] for r in b.data["results"]], [1, 2])

    def test_capabilities_list_new_flags(self):
        from core.capabilities import FEATURES

        self.assertIn("receipt_edit_discount", FEATURES)
        self.assertIn("receipt_edit_sale_price", FEATURES)


class ReceiptDiscountEditTests(ReceiptEditBase):
    """01.11: скидка шапки (discount / discount_percent) в правке прихода."""

    def test_discount_money_changes_total_debt_and_lines(self):
        r = self.patch({"discount": "20"})
        self.assertEqual(r.status_code, 200, r.data)
        dl = r.data["deltas"]
        self.assertEqual(dl["total"], {"before": "100.00", "after": "80.00", "delta": "-20.00"})
        self.assertEqual(dl["supplier_debt"]["delta"], "-20.00")
        self.assertEqual(dl["header"]["discount"], {"before": "0.00", "after": "20.00"})
        self.assertEqual(r.data["receipt"]["total_amount"], "80.00")
        rc = SupplierReceipt.objects.get(pk=self.rid)
        self.assertEqual((rc.discount, rc.discount_percent, rc.version), (Decimal("20.00"), None, 2))
        self.item.refresh_from_db()
        self.assertEqual((self.item.purchase_price, self.item.landed_price), (Decimal("8.0000"), Decimal("8.0000")))
        self.deal.refresh_from_db()
        self.assertEqual(self.deal.amount, Decimal("80.00"))
        self.p.refresh_from_db()
        self.assertEqual(self.p.purchase_price, Decimal("8.0000"))  # закупка в карточке — как при проведении
        v2 = SupplierReceiptVersion.objects.get(receipt_id=self.rid, version=2)
        self.assertEqual((v2.snapshot["discount"], v2.snapshot["total"]), ("20.00", "80.00"))
        self.assertEqual(SupplierReceiptVersion.objects.get(receipt_id=self.rid, version=1).snapshot["discount"], "0.00")

    def test_discount_percent_forms(self):
        r = self.patch({"discount": "10%"})
        self.assertEqual(r.status_code, 200, r.data)
        rc = SupplierReceipt.objects.get(pk=self.rid)
        self.assertEqual((rc.discount, rc.discount_percent), (Decimal("10.00"), Decimal("10.00")))
        self.assertEqual(r.data["deltas"]["total"]["after"], "90.00")
        r = self.patch({"discount_percent": "20"})
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data["deltas"]["total"], {"before": "90.00", "after": "80.00", "delta": "-10.00"})
        rc.refresh_from_db()
        self.assertEqual((rc.discount, rc.discount_percent), (Decimal("20.00"), Decimal("20.00")))

    def test_remove_discount_and_unchanged_is_noop(self):
        self.assertEqual(self.patch({"discount": "20"}).status_code, 200)
        r = self.patch({"discount": "20"})
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data["deltas"]["header"], {})
        self.assertEqual(r.data["deltas"]["total"]["delta"], "0.00")
        r = self.patch({"discount": 0})
        self.assertEqual(r.data["deltas"]["total"], {"before": "80.00", "after": "100.00", "delta": "20.00"})
        self.assertEqual(SupplierReceipt.objects.get(pk=self.rid).discount, Decimal("0.00"))
        self.item.refresh_from_db()
        self.assertEqual((self.item.purchase_price, self.item.landed_price), (Decimal("10.0000"), None))

    def test_discount_over_total_and_bad_values(self):
        self.assertEqual(self.code(self.patch({"discount": "150"}), 422), "discount_exceeds_total")
        self.assertEqual(self.code(self.patch({"discount": "-1"}), 422), "validation_error")
        self.assertEqual(self.code(self.patch({"discount_percent": "101"}), 422), "validation_error")

    def test_discount_dry_run_changes_nothing(self):
        r = self.patch({"discount": "30", "dry_run": True}, key=False)
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data["deltas"]["total"]["after"], "70.00")
        self.assertEqual(SupplierReceipt.objects.get(pk=self.rid).version, 1)
        self.assertEqual(SupplierReceipt.objects.get(pk=self.rid).discount, Decimal("0.00"))

    def test_discount_with_line_change_and_version_check(self):
        r = self.patch({"discount": "10%", "lines": [{"id": str(self.item.id), "qty": 5}]}, HTTP_IF_MATCH='"1"')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data["deltas"]["total"]["after"], "45.00")
        self.assertEqual(self.code(self.patch({"discount": "5"}, HTTP_IF_MATCH='"1"'), 412), "version_conflict")

    def test_edit_discount_set_at_creation(self):
        r = self.receive([{"product": str(self.p2.id), "qty": 10, "purchase_price": "10.00"}], discount="10")
        rid = r.data["id"]
        url = f"/api/main/suppliers/receipts/{rid}/"
        self.assertEqual(self.api.get(url).data["total_amount"], "90.00")
        resp = self.patch({"discount": "20"}, url=url)
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data["deltas"]["total"], {"before": "90.00", "after": "80.00", "delta": "-10.00"})
        self.assertEqual(SupplierReceiptItem.objects.get(receipt_id=rid).purchase_price, Decimal("8.0000"))

    def test_revert_restores_discount(self):
        self.assertEqual(self.patch({"discount": "20"}).status_code, 200)
        r = self.api.post(self.url + "revert/", {"to_version": 1, "reason": REASON, "version": 2}, format="json",
                          HTTP_IDEMPOTENCY_KEY=str(uuid.uuid4()))
        self.assertEqual(r.status_code, 200, r.data)
        rc = SupplierReceipt.objects.get(pk=self.rid)
        self.assertEqual((rc.discount, rc.version), (Decimal("0.00"), 3))
        self.assertEqual(r.data["receipt"]["total_amount"], "100.00")
        self.item.refresh_from_db()
        self.assertEqual(self.item.purchase_price, Decimal("10.0000"))

    def test_discount_permission_and_reason_rules_apply(self):
        _, admin = self.user(role="admin")
        self.assertEqual(self.code(self.patch({"discount": "5"}, api=admin), 403), "permission_denied")
        self.assertEqual(self.code(self.patch({"discount": "5", "reason": ""}), 400), "reason_required")


class ReceiptSalePriceEditTests(ReceiptEditBase):
    """01.11: цена продажи строки (sale_price) в правке прихода."""

    def test_sale_price_updates_line_and_product(self):
        r = self.patch({"lines": [{"id": str(self.item.id), "sale_price": "20"}]})
        self.assertEqual(r.status_code, 200, r.data)
        sp = r.data["deltas"]["sale_price"]
        self.assertEqual(len(sp), 1)
        self.assertEqual((sp[0]["line_id"], sp[0]["before"], sp[0]["after"], sp[0]["applied"]),
                         (str(self.item.id), "15.000", "20.000", True))
        self.assertEqual((sp[0]["product_price_before"], sp[0]["product_price_after"]), ("15.00", "20.00"))
        self.assertEqual(r.data["deltas"]["lines"][0]["sale_price_after"], "20.000")
        self.item.refresh_from_db()
        self.assertEqual((self.item.sale_price, self.item.previous_sale_price), (Decimal("20"), Decimal("15")))
        self.p.refresh_from_db()
        self.assertEqual((self.p.price, self.p.markup_percent), (Decimal("20.00"), Decimal("100.0000")))
        self.assertEqual(r.data["deltas"]["total"]["delta"], "0.00")
        snap = SupplierReceiptVersion.objects.get(receipt_id=self.rid, version=2).snapshot
        self.assertEqual(snap["lines"][0]["sale_price"], "20.000")

    def test_sale_price_flag_false_keeps_product(self):
        r = self.patch({"update_product_sale_price": False, "lines": [{"id": str(self.item.id), "sale_price": "25"}]})
        self.assertEqual(r.status_code, 200, r.data)
        self.assertFalse(r.data["deltas"]["sale_price"][0]["applied"])
        self.item.refresh_from_db()
        self.p.refresh_from_db()
        self.assertEqual((self.item.sale_price, self.p.price), (Decimal("25"), Decimal("15.00")))

    def test_sale_price_validation_and_dry_run(self):
        self.assertEqual(self.code(self.patch({"lines": [{"id": str(self.item.id), "sale_price": "-1"}]}), 422),
                         "validation_error")
        self.assertEqual(self.code(self.patch({"lines": [{"id": str(self.item.id), "sale_price": "abc"}]}), 422),
                         "validation_error")
        r = self.patch({"dry_run": True, "lines": [{"id": str(self.item.id), "sale_price": "30"}]}, key=False)
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data["deltas"]["sale_price"][0]["product_price_after"], "30.00")
        self.p.refresh_from_db()
        self.assertEqual(self.p.price, Decimal("15.00"))

    def test_sale_price_on_added_line(self):
        r = self.patch({"lines": [{"product": str(self.p2.id), "qty": 4, "purchase_price": "5", "sale_price": "9"}]})
        self.assertEqual(r.status_code, 200, r.data)
        it = SupplierReceiptItem.objects.get(receipt_id=self.rid, product=self.p2)
        self.assertEqual((it.sale_price, it.previous_sale_price), (Decimal("9"), Decimal("8")))
        self.p2.refresh_from_db()
        self.assertEqual(self.p2.price, Decimal("9.00"))

    def test_revert_restores_line_sale_price_but_not_product(self):
        self.assertEqual(self.patch({"lines": [{"id": str(self.item.id), "sale_price": "20"}]}).status_code, 200)
        r = self.api.post(self.url + "revert/", {"to_version": 1, "reason": REASON, "version": 2}, format="json",
                          HTTP_IDEMPOTENCY_KEY=str(uuid.uuid4()))
        self.assertEqual(r.status_code, 200, r.data)
        self.item.refresh_from_db()
        self.p.refresh_from_db()
        self.assertEqual(self.item.sale_price, Decimal("15"))
        self.assertEqual(self.p.price, Decimal("20.00"))  # откат документа карточку товара не трогает

    def test_sale_price_permission(self):
        _, admin = self.user(role="admin")
        r = self.patch({"lines": [{"id": str(self.item.id), "sale_price": "20"}]}, api=admin)
        self.assertEqual(self.code(r, 403), "permission_denied")
