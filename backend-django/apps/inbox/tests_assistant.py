"""ТЗ 01.11: ИИ-помощник витрины, защита от злоупотреблений, согласие, очистка."""
from datetime import timedelta
from decimal import Decimal
from unittest import mock

from django.core.cache import cache
from django.core.management import call_command
from django.test import override_settings
from django.utils import timezone

from apps.inbox import assistant, contacts
from apps.inbox.models import AssistantTurn, ChannelContact, ChatConsentLog, Message, WidgetSession
from apps.inbox.tests import BASE
from apps.inbox.tests_core import Mixin
from apps.inbox.tests_widget import PUB, WidgetBase
from apps.main.models import Product, ProductVariant
from apps.main.telegram_bot.models import TelegramBotSettings

MODEL = "apps.inbox.assistant._call_model"
KEY = "AIza-SECRET-SHOP-KEY"


def fake(tool=None, args=None, text="Ок"):
    seen = {}

    def fn(api_key, system, contents, execute):
        seen["key"] = api_key
        if tool:
            execute(tool, args or {})
        return text, "gemini-test", [tool] if tool else []
    fn.seen = seen
    return fn


class AssistantBase(Mixin, WidgetBase):
    def setUp(self):
        super().setUp()
        cache.clear()
        bs = TelegramBotSettings.objects.create(company=self.company, mode=TelegramBotSettings.Mode.SERVER)
        bs.ai_key = KEY
        bs.save()
        self.p = Product.objects.create(company=self.company, name="Платье синее", price=Decimal("1900"), quantity=Decimal("5"))
        self.v = ProductVariant.objects.create(company=self.company, product=self.p, size="M", color="синий",
                                               quantity=Decimal("3"), price=Decimal("1900"))
        r = self.api.put(f"{BASE}/assistant/settings/", {"enabled": True, "daily_cap": 100}, format="json")
        self.assertEqual(r.status_code, 200, r.content)
        self.s = self.new_session()

    def ask(self, text="Сколько стоит платье?", s=None, **extra):
        s = s or self.s
        return self.anon.post(f"{PUB}/sessions/{s['session_id']}/assistant/", {"text": text, **extra}, format="json",
                              HTTP_X_VISITOR_TOKEN=s["visitor_token"])


class SettingsTests(AssistantBase):
    def test_settings_never_expose_key(self):
        r = self.api.get(f"{BASE}/assistant/settings/")
        self.assertTrue(r.json()["key_set"])
        self.assertNotIn(KEY, r.content.decode())

    def test_knowledge_limit_and_langs(self):
        r = self.api.put(f"{BASE}/assistant/settings/", {"knowledge": {"ru": "x" * 2001}}, format="json")
        self.assertEqual(r.status_code, 400)
        r = self.api.put(f"{BASE}/assistant/settings/", {"knowledge": {"de": "x"}}, format="json")
        self.assertEqual(r.status_code, 400)
        r = self.api.put(f"{BASE}/assistant/settings/", {"knowledge": {"ru": "Возврат 14 дней", "kk": "Қайтару"}}, format="json")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["knowledge"]["ru"], "Возврат 14 дней")

    def test_test_question(self):
        with mock.patch(MODEL, fake("get_shop_info", {}, "Привет")):
            r = self.api.post(f"{BASE}/assistant/test/", {"text": "Привет"}, format="json")
        self.assertTrue(r.json()["ok"])
        self.assertFalse(AssistantTurn.objects.filter(counted=True).exists())

    def test_capabilities_flags(self):
        from core.capabilities import FEATURES
        self.assertIn("showcase_assistant", FEATURES)
        self.assertIn("showcase_chat", FEATURES)


class AskTests(AssistantBase):
    def test_no_key_unavailable_with_handoff(self):
        TelegramBotSettings.objects.update(encrypted_ai_key="")
        with mock.patch(MODEL) as m:
            r = self.ask().json()
        m.assert_not_called()
        self.assertTrue(r["unavailable"])
        self.assertIn("contacts", r["handoff"])

    def test_disabled_and_global_kill(self):
        self.api.put(f"{BASE}/assistant/settings/", {"enabled": False}, format="json")
        self.assertTrue(self.ask().json()["unavailable"])
        self.api.put(f"{BASE}/assistant/settings/", {"enabled": True}, format="json")
        with mock.patch.dict("os.environ", {"SHOWCASE_ASSISTANT_DISABLED": "1"}), mock.patch(MODEL) as m:
            self.assertTrue(self.ask("другой вопрос").json()["unavailable"])
        m.assert_not_called()

    def test_uses_shop_key_only_and_no_leak(self):
        f = fake("search_products", {"query": "платье"}, "Платье стоит 1900 сом.")
        with mock.patch(MODEL, f):
            r = self.ask()
        self.assertEqual(f.seen["key"], KEY)
        self.assertNotIn(KEY, r.content.decode())
        j = r.json()
        self.assertEqual(j["status"], "ok")
        self.assertEqual(j["cards"][0]["price"], "1900.000")
        self.assertEqual(j["cards"][0]["variants"][0]["size"], "M")

    def test_global_key_never_used(self):
        TelegramBotSettings.objects.update(encrypted_ai_key="")
        with mock.patch.dict("os.environ", {"GEMINI_API_KEY": "GLOBAL"}), mock.patch(MODEL) as m:
            self.assertTrue(self.ask().json()["unavailable"])
        m.assert_not_called()

    def test_hallucinated_price_blocked(self):
        with mock.patch(MODEL, fake("search_products", {"query": "платье"}, "Платье стоит 1500 сом.")):
            j = self.ask().json()
        self.assertEqual(j["answer"], assistant.UNKNOWN_TEXT)
        t = AssistantTurn.objects.filter(outcome="answered").last()
        self.assertEqual(t.blocked, "hallucination_blocked")
        self.assertEqual(t.tools, ["search_products"])

    def test_number_without_tool_blocked(self):
        with mock.patch(MODEL, fake(None, None, "Осталось 3 штуки, цена 1900")):
            self.assertEqual(self.ask().json()["answer"], assistant.UNKNOWN_TEXT)

    def test_add_to_cart_returns_line_and_total_checked(self):
        with mock.patch(MODEL, fake("add_to_cart", {"product": str(self.p.id), "variant": "M", "qty": 2},
                                    "Добавила 2 шт, сумма 3800 сом.")):
            j = self.ask("Положи два платья M").json()
        line = j["cart_actions"][0]
        self.assertEqual((line["product"], line["variant"], line["qty"], line["line_total"]),
                         (str(self.p.id), str(self.v.id), 2, "3800.00"))
        self.assertIn("3800", j["answer"])

    def test_add_to_cart_needs_variant(self):
        with mock.patch(MODEL, fake("add_to_cart", {"product": str(self.p.id)}, "Какой размер?")):
            j = self.ask("в корзину").json()
        self.assertEqual(j["cart_actions"], [])

    def test_shop_info_knowledge_and_handoff(self):
        self.api.put(f"{BASE}/assistant/settings/", {"knowledge": {"ru": "Обмен в течение 14 дней"}}, format="json")
        seen = {}

        def fn(api_key, system, contents, execute):
            seen["info"] = execute("get_shop_info", {})
            execute("handoff", {"reason": "жалоба"})
            return "Позвала продавца", "m", []
        with mock.patch(MODEL, fn):
            j = self.ask("обмен?").json()
        self.assertEqual(seen["info"]["rules"], "Обмен в течение 14 дней")
        self.assertTrue(j["handoff"]["requested"])
        self.assertTrue(j["handoff"]["contacts"]["chat"])

    def test_size_chart_tool(self):
        from apps.main.models import SizeChart
        ch = SizeChart.objects.create(company=self.company, name="Платья", columns=["Размер", "Грудь"], rows=[["M", "90"]])
        self.p.size_chart = ch
        self.p.save()
        out = {}

        def fn(api_key, system, contents, execute):
            out["r"] = execute("get_size_chart", {"product": str(self.p.id)})
            return "Таблица ниже", "m", []
        with mock.patch(MODEL, fn):
            self.ask("размеры")
        self.assertEqual(out["r"]["size_chart"]["rows"], [["M", "90"]])

    def test_staff_sees_messages_and_visitor_sees_answer(self):
        with mock.patch(MODEL, fake(None, None, "Здравствуйте")):
            self.ask("Привет")
        senders = list(Message.objects.order_by("id").values_list("sender", flat=True))
        self.assertIn("ai", senders)
        r = self.anon.get(f"{PUB}/sessions/{self.s['session_id']}/messages/?wait=0",
                          HTTP_X_VISITOR_TOKEN=self.s["visitor_token"])
        self.assertEqual([m["sender"] for m in r.json()["results"]], ["visitor", "assistant"])

    @override_settings(CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}})
    def test_cache_same_question(self):
        m = mock.Mock(side_effect=fake(None, None, "Работаем каждый день"))
        with mock.patch(MODEL, m):
            self.ask("Когда работаете?")
            j = self.ask("  когда   работаете? ", s=self.new_session(ip="3.3.3.3")).json()
        self.assertEqual(m.call_count, 1)
        self.assertTrue(j.get("cached"))


class LimitTests(AssistantBase):
    def run_asks(self, n, s=None):
        out = None
        with mock.patch(MODEL, fake(None, None, "Ок")):
            for i in range(n):
                out = self.ask(f"вопрос {i}", s=s).json()
        return out

    def test_session_6_per_minute(self):
        self.assertEqual(self.run_asks(6)["status"], "ok")
        j = self.run_asks(1)
        self.assertTrue(j["busy"])
        self.assertEqual(j["reason"], "session_minute")
        self.assertIn("contacts", j["handoff"])

    def test_session_40_per_day(self):
        sess = WidgetSession.objects.get(pk=self.s["session_id"])
        AssistantTurn.objects.bulk_create([AssistantTurn(company=self.company, session=sess, outcome="answered")
                                           for _ in range(40)])
        AssistantTurn.objects.update(created_at=timezone.now() - timedelta(hours=2))
        j = self.run_asks(1)
        self.assertEqual(j["reason"], "session_day")

    def test_ip_day_limit(self):
        AssistantTurn.objects.bulk_create([AssistantTurn(company=self.company, ip="5.5.5.5", outcome="answered")
                                           for _ in range(120)])
        s2 = self.new_session(ip="5.5.5.5")
        with mock.patch(MODEL, fake(None, None, "Ок")):
            j = self.anon.post(f"{PUB}/sessions/{s2['session_id']}/assistant/", {"text": "привет"}, format="json",
                               HTTP_X_VISITOR_TOKEN=s2["visitor_token"], REMOTE_ADDR="5.5.5.5").json()
        self.assertEqual(j["reason"], "ip_day")

    def test_shop_daily_cap(self):
        self.api.put(f"{BASE}/assistant/settings/", {"daily_cap": 2}, format="json")
        j = self.run_asks(3)
        self.assertEqual(j["reason"], "shop_day")


class TurnstileTests(AssistantBase):
    def test_skipped_without_secret(self):
        self.assertTrue(assistant.turnstile_verify("", "1.1.1.1"))

    def test_required_with_secret(self):
        with mock.patch.dict("os.environ", {"TURNSTILE_SECRET_KEY": "s"}):
            r = self.anon.post(f"{PUB}/sessions/", {}, format="json", REMOTE_ADDR="7.7.7.7")
            self.assertEqual(r.status_code, 403)
            with mock.patch("httpx.post") as post:
                post.return_value.status_code = 200
                post.return_value.json.return_value = {"success": True}
                r = self.anon.post(f"{PUB}/sessions/", {"turnstile_token": "tok"}, format="json", REMOTE_ADDR="7.7.7.7")
            self.assertEqual(r.status_code, 201)


class DataTests(AssistantBase):
    def test_consent_required_and_logged(self):
        url = f"{PUB}/sessions/{self.s['session_id']}/consent/"
        h = {"HTTP_X_VISITOR_TOKEN": self.s["visitor_token"]}
        self.assertEqual(self.anon.post(url, {"phone": "+996700111222"}, format="json", **h).status_code, 400)
        self.assertEqual(self.anon.post(url, {"phone": "+996700111222", "consent": False}, format="json", **h).status_code, 400)
        r = self.anon.post(url, {"phone": "+996700111222", "consent": True, "name": "Аня"}, format="json", **h)
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(ChatConsentLog.objects.filter(consent=True).count(), 1)
        self.assertTrue(ChannelContact.objects.get(pk=WidgetSession.objects.get().contact_id).phone)

    def test_delete_my_chat(self):
        with mock.patch(MODEL, fake(None, None, "Ок")):
            self.ask("секретный вопрос")
        sid = self.s["session_id"]
        r = self.anon.delete(f"{PUB}/sessions/{sid}/", HTTP_X_VISITOR_TOKEN="x" * 43)
        self.assertEqual(r.status_code, 401)
        r = self.anon.delete(f"{PUB}/sessions/{sid}/", HTTP_X_VISITOR_TOKEN=self.s["visitor_token"])
        self.assertEqual(r.status_code, 200)
        self.assertFalse(WidgetSession.objects.exists())
        self.assertFalse(Message.objects.exists())
        self.assertEqual(AssistantTurn.objects.exclude(question="").count(), 0)

    def test_purge_idempotent(self):
        old = WidgetSession.objects.get()
        WidgetSession.objects.filter(pk=old.pk).update(created_at=timezone.now() - timedelta(days=91))
        s_new = self.new_session(ip="9.9.9.9")
        call_command("purge_showcase_chats", stdout=mock.Mock())
        self.assertFalse(WidgetSession.objects.filter(pk=old.pk).exists())
        self.assertTrue(WidgetSession.objects.filter(pk=s_new["session_id"]).exists())
        res = assistant.purge_old()
        self.assertEqual(res["contacts"], 0)

    def test_telegram_start_links_session(self):
        s = WidgetSession.objects.get()
        s.link_token = "T" * 32
        s.save()
        ch = self.mk_channel(kind="telegram_bot")
        contact, _ = contacts.get_or_create_contact(ch, "555", display_name="Tg", start_payload="w_" + "T" * 32)
        s.refresh_from_db()
        self.assertEqual(s.tg_contact_id, contact.id)
