"""ТЗ 01.11.2026 (витрина P0): telegram-блок, source_detail, ссылка на корзину, события, округление."""
import uuid
from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

from django.core.cache import cache
from django.utils import timezone

from apps.main.models import SaleItem, ShowcaseCartLink, ShowcaseOrder, ShowcaseStats
from apps.main.telegram_bot.models import TelegramBotSettings
from apps.main.tests_showcase_editor_v2 import DRAFT, ShowcaseEditorV2Base

TG = "apps.main.telegram_bot.services.telegram_api."


class TelegramBlockTests(ShowcaseEditorV2Base):
    def bot(self, **kw):
        defaults = dict(mode="server", webhook_ok=True, bot_username="nbs_shop_bot")
        defaults.update(kw)
        row, _ = TelegramBotSettings.objects.update_or_create(company=self.company, defaults=defaults)
        return row

    def enable_in_design(self, **tg):
        body = {"enabled": True, "placement": ["cart", "product"], "label": {"ru": "Заказать"}}
        body.update(tg)
        res = self.api.patch(DRAFT, {"cart": {"telegram": body}}, format="json")
        self.assertEqual(res.status_code, 200, res.content)
        self.publish()

    def block(self):
        res = self.public_design()
        self.assertEqual(res.status_code, 200)
        return res.data["telegram"]

    def test_disabled_by_default(self):
        self.bot()
        self.publish()
        self.assertFalse(self.block()["enabled"])

    def test_enabled_when_bot_server_webhook_and_owner_flag(self):
        self.bot()
        self.enable_in_design()
        b = self.block()
        self.assertEqual(b["enabled"], True)
        self.assertEqual(b["url"], "https://t.me/nbs_shop_bot")
        self.assertEqual(b["product_url_template"], "https://t.me/nbs_shop_bot?start=p_{id}")
        self.assertEqual(b["placement"], ["cart", "product"])
        self.assertNotIn("token", str(self.public_design().content).lower().replace("tokens", ""))

    def test_off_in_local_mode_without_webhook_or_owner_flag(self):
        self.enable_in_design()
        self.bot(mode="local")
        self.assertFalse(self.block()["enabled"])
        self.bot(mode="server", webhook_ok=False)
        self.assertFalse(self.block()["enabled"])
        self.bot(webhook_ok=True)
        self.assertTrue(self.block()["enabled"])  # кэш не залип: состояние бота в ключе
        self.api.patch(DRAFT, {"cart": {"telegram": {"enabled": False}}}, format="json")
        self.publish()
        self.assertFalse(self.block()["enabled"])

    def test_no_bot_at_all(self):
        self.enable_in_design()
        self.assertFalse(self.block()["enabled"])

    def test_bad_placement_rejected(self):
        res = self.api.patch(DRAFT, {"cart": {"telegram": {"placement": ["nowhere"]}}}, format="json")
        self.assertEqual(res.status_code, 400)


class OrderSourceDetailTests(ShowcaseEditorV2Base):
    def order(self, **extra):
        body = {"customer": {"name": "A", "phone": "+996555123456"},
                "items": [{"product": str(self.apple.id), "qty": "1"}]}
        body.update(extra)
        return self.pub.post(self.public_url("orders/"), body, format="json")

    def test_source_detail_and_web_chat(self):
        r = self.order(source="web_chat", source_detail="assistant")
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual((r.data["source"], r.data["source_detail"]), ("web_chat", "assistant"))
        o = ShowcaseOrder.objects.get(id=r.data["id"])
        self.assertEqual((o.source, o.source_detail), ("web_chat", "assistant"))

    def test_bad_source_detail_rejected(self):
        self.assertEqual(self.order(source_detail="bad detail!").status_code, 400)

    def test_list_filter_and_serializer(self):
        self.order(source="web_chat", source_detail="assistant")
        self.pub.post(self.public_url("orders/"), {"customer": {"name": "B", "phone": "+996555123457"},
                      "items": [{"product": str(self.pear.id), "qty": "1"}], "source_detail": "product_card"}, format="json")
        res = self.api.get("/api/main/showcase/orders/", {"source_detail": "assistant"})
        self.assertEqual(res.status_code, 200, res.content)
        rows = res.data if isinstance(res.data, list) else res.data["results"]
        self.assertEqual([r["source_detail"] for r in rows], ["assistant"])
        self.assertEqual(rows[0]["source"], "web_chat")
        self.assertIn("cart_token", rows[0])
        all_rows = self.api.get("/api/main/showcase/orders/").data
        self.assertEqual(len(all_rows if isinstance(all_rows, list) else all_rows["results"]), 2)


class CartLinkTests(ShowcaseEditorV2Base):
    URL = "cart-link/"

    def link(self, items=None):
        items = items if items is not None else [{"product": str(self.apple.id), "qty": "2"}]
        return self.pub.post(self.public_url(self.URL), {"items": items}, format="json")

    def test_create_link(self):
        r = self.link()
        self.assertEqual(r.status_code, 201, r.content)
        tok = r.data["token"]
        self.assertRegex(tok, r"^[A-Za-z0-9_-]{1,55}$")
        self.assertLessEqual(len("c_" + tok), 64)
        row = ShowcaseCartLink.objects.get(token=tok)
        self.assertEqual(row.items, [{"product": str(self.apple.id), "variant": None, "qty": "2.000"}])
        self.assertGreater(row.expires_at, timezone.now() + timedelta(days=6))
        self.assertNotIn("price", str(row.items))
        self.assertEqual(ShowcaseStats.objects.get(company=self.company).cart_link, 1)

    def test_validation_and_rate_limit(self):
        self.assertEqual(self.link(items=[]).status_code, 400)
        r = self.link(items=[{"product": str(uuid.uuid4()), "qty": "1"}])
        self.assertEqual((r.status_code, r.data["code"]), (400, "product_not_found"))
        cache.clear()
        for _ in range(20):
            self.assertEqual(self.link().status_code, 201)
        self.assertEqual(self.link().status_code, 429)

    def test_order_with_cart_token_is_once(self):
        tok = self.link().data["token"]
        body = {"customer": {"name": "A", "phone": "+996555123456"},
                "items": [{"product": str(self.apple.id), "qty": "2"}], "cart_token": tok,
                "source": "telegram_bot", "telegram_chat_id": "555"}
        r1 = self.pub.post(self.public_url("orders/"), body, format="json")
        r2 = self.pub.post(self.public_url("orders/"), body, format="json")
        self.assertEqual((r1.status_code, r2.status_code), (201, 200), r1.content)
        self.assertEqual(r1.data["id"], r2.data["id"])
        o = ShowcaseOrder.objects.get(id=r1.data["id"])
        self.assertEqual((o.source, o.source_detail, o.cart_token), ("telegram_bot", "site_cart", tok))
        self.assertEqual(ShowcaseOrder.objects.filter(company=self.company).count(), 1)

    def test_unknown_cart_token_rejected(self):
        body = {"customer": {"name": "A", "phone": "+996555123456"},
                "items": [{"product": str(self.apple.id), "qty": "1"}], "cart_token": "nope"}
        r = self.pub.post(self.public_url("orders/"), body, format="json")
        self.assertEqual((r.status_code, r.data["code"]), (400, "cart_link_not_found"))


class CartLinkBotTests(ShowcaseEditorV2Base):
    def setUp(self):
        super().setUp()
        self.bot = TelegramBotSettings.objects.create(
            company=self.company, mode="server", webhook_ok=True, bot_username="nbs_bot", owner_chat_id="1", token="1:TEST")
        self.patches = {}
        for name in ("send_message", "send_photo", "edit_message_reply_markup", "answer_callback_query", "edit_message_text"):
            p = patch(TG + name, return_value={"ok": True, "result": {"message_id": 5}})
            self.patches[name] = p.start()
            self.addCleanup(p.stop)

    def start(self, arg):
        from apps.main.telegram_bot.services import customer_handler
        customer_handler.handle_customer_message(self.bot, "777", {"first_name": "Тест"}, f"/start {arg}")

    def texts(self):
        return [c.args[2] for c in self.patches["send_message"].call_args_list if len(c.args) > 2]

    def callback(self, data):
        from apps.main.telegram_bot.services import callback_handler
        callback_handler.handle_callback_query(self.bot, {
            "id": "1", "from": {"id": 777, "first_name": "Тест"}, "data": data,
            "message": {"chat": {"id": 777}, "message_id": 9}})

    def _draft_ids(self):
        for c in self.patches["send_message"].call_args_list:
            markup = c.kwargs.get("reply_markup") or {}
            for row in markup.get("inline_keyboard", []):
                for b in row:
                    if b["callback_data"].startswith("ord:confirm:"):
                        yield b["callback_data"].split(":", 2)[2]

    def test_start_cart_uses_db_prices_and_places_order_once(self):
        ShowcaseCartLink.objects.create(
            company=self.company, token="tok123",
            items=[{"product": str(self.apple.id), "variant": None, "qty": "2", "price": "1"}],
            expires_at=timezone.now() + timedelta(days=1))
        self.start("c_tok123")
        summary = "\n".join(self.texts())
        self.assertIn("Яблоко", summary)
        self.assertIn("200", summary)  # цена 100 из базы, а не «1» из ссылки
        draft_id = next(iter(self._draft_ids()))
        self.callback(f"ord:confirm:{draft_id}")
        o = ShowcaseOrder.objects.get(company=self.company)
        self.assertEqual((o.source, o.source_detail, o.cart_token, o.total),
                         ("telegram_bot", "site_cart", "tok123", Decimal("200.00")))
        self.start("c_tok123")  # повторное открытие ссылки — заказ уже есть, нового нет
        self.assertIn("уже оформлен", self.texts()[-1])
        self.assertEqual(ShowcaseOrder.objects.filter(company=self.company).count(), 1)

    def test_double_confirm_makes_one_order(self):
        ShowcaseCartLink.objects.create(
            company=self.company, token="tok777", items=[{"product": str(self.apple.id), "variant": None, "qty": "1"}],
            expires_at=timezone.now() + timedelta(days=1))
        self.start("c_tok777")
        draft_id = next(iter(self._draft_ids()))
        self.callback(f"ord:confirm:{draft_id}")
        self.callback(f"ord:confirm:{draft_id}")
        self.assertEqual(ShowcaseOrder.objects.filter(company=self.company).count(), 1)

    def test_expired_and_unknown_link(self):
        ShowcaseCartLink.objects.create(company=self.company, token="old", items=[],
                                        expires_at=timezone.now() - timedelta(seconds=1))
        self.start("c_old")
        self.assertIn("устарела", self.texts()[-1])
        self.start("c_missing")
        self.assertIn("устарела", self.texts()[-1])
        self.assertFalse(ShowcaseOrder.objects.exists())

    def test_start_product_card(self):
        self.start(f"p_{self.apple.id}")
        self.assertTrue(any("Яблоко" in str(c) for c in self.patches["send_message"].call_args_list))
        self.start("p_00000000-0000-0000-0000-000000000000")
        self.assertIn("не найден", self.texts()[-1])


class EventsTests(ShowcaseEditorV2Base):
    def test_new_event_counters(self):
        for t in ("assistant_open", "assistant_message", "assistant_message", "telegram_click", "cart_link"):
            r = self.pub.post(self.public_url("showcase/events/"), {"type": t}, format="json")
            self.assertEqual(r.status_code, 200, (t, r.content))
        st = ShowcaseStats.objects.get(company=self.company)
        self.assertEqual((st.assistant_open, st.assistant_message, st.telegram_click, st.cart_link), (1, 2, 1, 1))
        res = self.api.get("/api/main/showcase/stats/")
        self.assertEqual(res.status_code, 200, res.content)
        self.assertEqual((res.data["assistant_message"], res.data["telegram_click"]), (2, 1))

    def test_unknown_event_rejected(self):
        r = self.pub.post(self.public_url("showcase/events/"), {"type": "nope"}, format="json")
        self.assertEqual(r.status_code, 400)


class RoundingAndCapabilitiesTests(ShowcaseEditorV2Base):
    def test_line_total_half_up(self):
        item = SaleItem(unit_price=Decimal("0.05"), quantity=Decimal("0.1"), line_discount=Decimal("0"))
        self.assertEqual(item.line_total, Decimal("0.01"))  # 0.005 -> 0.01 (раньше 0.00)
        item = SaleItem(unit_price=Decimal("2.50"), quantity=Decimal("0.01"), line_discount=Decimal("0"))
        self.assertEqual(item.line_total, Decimal("0.03"))  # 0.025 -> 0.03

    def test_cart_service_money_half_up(self):
        from apps.main.cart_service import _money
        self.assertEqual(_money(Decimal("0.125")), Decimal("0.13"))
        self.assertEqual(_money(Decimal("0.005")), Decimal("0.01"))

    def test_capabilities_flags(self):
        from core.capabilities import FEATURES
        for f in ("showcase_telegram", "showcase_cart_link", "showcase_order_source_detail"):
            self.assertIn(f, FEATURES)


class ShopKnowledgeTests(ShowcaseEditorV2Base):
    def test_knowledge_saved_published_private(self):
        from apps.main.showcase import services as svc
        res = self.api.patch(DRAFT, {"shop": {"info": {"knowledge": {"ru": "Доставка бесплатно", "ky": "Акысыз"}}}}, format="json")
        self.assertEqual(res.status_code, 200, res.content)
        self.assertEqual(svc.get_shop_knowledge(self.company, "ru"), "")  # черновик не виден, пока не опубликован
        self.publish()
        self.assertEqual(svc.get_shop_knowledge(self.company, "ky"), "Акысыз")
        self.assertEqual(svc.get_shop_knowledge(self.company, "en"), "Доставка бесплатно")  # запасной ru
        body = self.public_design().content.decode()
        self.assertNotIn("Доставка бесплатно", body)
        self.assertNotIn("knowledge", body)
        self.assertNotIn("shop", self.public_design().data)

    def test_knowledge_length_and_language_validated(self):
        too_long = self.api.patch(DRAFT, {"shop": {"info": {"knowledge": {"ru": "я" * 2001}}}}, format="json")
        self.assertEqual(too_long.status_code, 400)
        ok = self.api.patch(DRAFT, {"shop": {"info": {"knowledge": {"kk": "я" * 2000}}}}, format="json")
        self.assertEqual(ok.status_code, 200, ok.content)
        bad_lang = self.api.patch(DRAFT, {"shop": {"info": {"knowledge": {"fr": "x"}}}}, format="json")
        self.assertEqual(bad_lang.status_code, 400)
