"""ТЗ 31.10 п.14: единый словарь событий, supplier_debt_changed в потоке."""
import uuid
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.main import event_names as en
from apps.main.change_feed import serialize_event
from apps.main.events_stream import to_stream_event
from apps.main.models import ChangeEvent, Client, Product
from apps.users.models import Company

User = get_user_model()
BASE = {"id": 5, "at": "2026-10-31T10:00:00+06:00", "branch": None, "actor": None, "entity": "", "entity_id": ""}


class UnifiedNamesTests(TestCase):
    def test_unified_name(self):
        self.assertEqual(en.unified_name("product_changed", {"what": "price"}), "price_changed")
        self.assertEqual(en.unified_name("product_changed", {"what": "created"}), "product_changed")
        self.assertEqual(en.unified_name("sale_paid"), "sale_created")
        self.assertEqual(en.unified_name("debt_paid"), "debt_changed")
        self.assertEqual(en.unified_name("supplier_debt_changed"), "supplier_debt_changed")

    def test_stream_and_feed_use_same_names(self):
        """Для каждого типа ленты имя в потоке совпадает с единым именем."""
        cases = [
            ("sale_paid", {"sale": "S"}), ("sale_returned", {"sale": "S"}), ("shift_opened", {"shift": "X"}),
            ("shift_closed", {"shift": "X"}), ("cash_moved", {}), ("app_settings_changed", {"app": "a"}),
            ("debt_created", {"client": "C"}), ("debt_paid", {"client": "C"}), ("features_changed", {}),
            ("product_changed", {"what": "price", "product": "P"}),
            ("product_changed", {"what": "created", "product": "P"}),
            ("stock_changed", {"product": "P"}), ("staff_changed", {}), ("client_changed", {}),
            ("bonus_changed", {}), ("supplier_debt_changed", {"supplier": "SUP"}),
        ]
        for t, d in cases:
            ev = {**BASE, "type": t, "data": d}
            msg = to_stream_event(ev)
            self.assertIsNotNone(msg, t)
            self.assertEqual(msg["type"], en.unified_name(t, d), t)
            self.assertEqual(msg["feed_type"], t)

    def test_supplier_debt_in_stream(self):
        msg = to_stream_event({**BASE, "type": "supplier_debt_changed", "data": {"supplier": "SUP"}})
        self.assertEqual((msg["type"], msg["ids"], msg["supplier"]), ("supplier_debt_changed", ["SUP"], "SUP"))


class ChangesFeedEventFieldTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(email=f"e-{uuid.uuid4().hex}@t.com", password="x", role="owner")
        self.company = Company.objects.create(name="Co", owner=self.user)
        self.user.company = self.company
        self.user.save()
        self.api = APIClient()
        self.api.force_authenticate(self.user)

    def test_event_field_and_types_filter(self):
        cursor = self.api.get("/api/main/changes/").data["cursor"]
        with self.captureOnCommitCallbacks(execute=True):
            p = Product.objects.create(name="T", company=self.company, quantity=1, purchase_price=1, price=2)
        p = Product.objects.get(pk=p.pk)
        p.price = Decimal("5.00")
        with self.captureOnCommitCallbacks(execute=True):
            p.save()
        rows = self.api.get("/api/main/changes/", {"since": cursor}).data["events"]
        price = [e for e in rows if e["type"] == "product_changed" and e["data"].get("what") == "price"]
        self.assertEqual(price[0]["event"], "price_changed")
        by_unified = self.api.get("/api/main/changes/", {"since": cursor, "types": "price_changed"}).data["events"]
        self.assertTrue(by_unified)
        self.assertEqual(serialize_event(ChangeEvent.objects.filter(type="product_changed").first())["type"],
                         "product_changed")

    def test_supplier_debt_event_on_pay(self):
        sup = Client.objects.create(full_name="Пост", phone="+996700000001", type=Client.StatusClient.SUPPLIERS,
                                    company=self.company)
        from apps.integrations.events import emit_event
        with self.captureOnCommitCallbacks(execute=True):
            emit_event(self.company.id, "supplier_debt_changed", {"supplier": sup.id, "actor": self.user.id})
        ev = ChangeEvent.objects.get(type="supplier_debt_changed")
        self.assertEqual((ev.entity, ev.entity_id), ("supplier", str(sup.id)))
        self.assertEqual(serialize_event(ev)["event"], "supplier_debt_changed")
