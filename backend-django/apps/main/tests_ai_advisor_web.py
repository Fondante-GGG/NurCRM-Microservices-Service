from unittest import mock

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from apps.main.telegram_bot.models import TelegramBotSettings
from apps.users.models import Company

User = get_user_model()
GOOD = "AIzaSyTEST_" + "x" * 28


@override_settings(CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}})
class AiAdvisorWebTests(TestCase):
    def setUp(self):
        cache.clear()
        self.owner = User.objects.create_user(email="owner@adv.test", password="p12345678", role="owner")
        self.company = Company.objects.create(name="Adv Shop", slug="adv-shop", owner=self.owner)
        self.owner.company = self.company
        self.owner.owned_company = self.company
        self.owner.save()
        self.a = User.objects.create_user(email="a@adv.test", password="p12345678", role="admin", company=self.company)
        self.b = User.objects.create_user(email="b@adv.test", password="p12345678", company=self.company)
        self.c = User.objects.create_user(email="c@adv.test", password="p12345678", company=self.company)
        self.o = APIClient(); self.o.force_authenticate(self.owner)

    def as_user(self, u):
        c = APIClient(); c.force_authenticate(u); return c

    def test_status_owner_without_key(self):
        r = self.o.get("/api/users/ai-advisor/")
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.data["is_owner"]); self.assertTrue(r.data["can_use"]); self.assertFalse(r.data["configured"])

    def test_employee_cannot_use_or_configure_by_default(self):
        u = self.as_user(self.a)  # даже администратор
        self.assertFalse(u.get("/api/users/ai-advisor/").data["can_use"])
        self.assertEqual(u.post("/api/users/ai-advisor/ask/", {"question": "x"}, format="json").status_code, 403)
        self.assertEqual(u.get("/api/users/ai-advisor/settings/").status_code, 403)
        self.assertEqual(u.put("/api/users/ai-advisor/settings/", {"length": "short"}, format="json").status_code, 403)

    def test_owner_allows_two_people_not_three(self):
        r = self.o.put("/api/users/ai-advisor/settings/", {"allowed_user_ids": [str(self.a.pk), str(self.b.pk), str(self.c.pk)]}, format="json")
        self.assertEqual(r.status_code, 400)
        r = self.o.put("/api/users/ai-advisor/settings/", {"allowed_user_ids": [str(self.a.pk), str(self.b.pk)]}, format="json")
        self.assertEqual(r.status_code, 200)
        self.assertEqual({u["id"] for u in r.data["allowed_users"]}, {str(self.a.pk), str(self.b.pk)})
        self.assertTrue(self.as_user(self.b).get("/api/users/ai-advisor/").data["can_use"])
        self.assertFalse(self.as_user(self.c).get("/api/users/ai-advisor/").data["can_use"])
        # разрешённый не видит настроек
        self.assertEqual(self.as_user(self.b).get("/api/users/ai-advisor/settings/").status_code, 403)

    def test_foreign_user_is_ignored(self):
        other_owner = User.objects.create_user(email="x@other.test", password="p12345678")
        Company.objects.create(name="Other", slug="other", owner=other_owner)
        r = self.o.put("/api/users/ai-advisor/settings/", {"allowed_user_ids": [str(other_owner.pk)]}, format="json")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["allowed_users"], [])

    def test_main_key_is_shared_with_telegram_bot_and_masked(self):
        r = self.o.put("/api/users/ai-advisor/settings/", {"main_key": GOOD}, format="json")
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.data["main_key"]["set"])
        self.assertNotIn(GOOD, str(r.data))
        self.assertEqual(TelegramBotSettings.objects.get(company=self.company).ai_key, GOOD)

    def test_extra_keys_encrypted_kept_on_resave(self):
        r = self.o.put("/api/users/ai-advisor/settings/", {"keys": [{"label": "Аккаунт 2", "key": GOOD, "enabled": True}]}, format="json")
        kid = r.data["keys"][0]["id"]
        self.assertNotIn(GOOD, str(r.data))
        r = self.o.put("/api/users/ai-advisor/settings/", {"keys": [{"id": kid, "label": "Новое имя", "enabled": False}]}, format="json")
        self.assertEqual(r.data["keys"][0]["label"], "Новое имя")
        self.assertFalse(r.data["keys"][0]["enabled"])
        from apps.main import ai_advisor_web as w
        self.assertEqual(w._extra_keys(self.company)[0]["key"], GOOD)

    def test_ask_needs_key(self):
        r = self.o.post("/api/users/ai-advisor/ask/", {"question": "Сколько продал?"}, format="json")
        self.assertEqual(r.status_code, 409)

    def test_ask_rotates_to_next_key_and_counts_limit(self):
        self.o.put("/api/users/ai-advisor/settings/", {"main_key": "AIzaMAIN_" + "y" * 30, "daily_limit": 2,
                                                       "keys": [{"label": "2", "key": GOOD, "enabled": True}]}, format="json")
        calls = []

        def fake(api_key, **kw):
            calls.append(api_key)
            if api_key.startswith("AIzaMAIN"):
                raise RuntimeError("HTTP 429 RESOURCE_EXHAUSTED")
            return "Выручка **1 250 сом**", "m", ["get_sales_summary"]

        with mock.patch("apps.main.telegram_bot.services.ai_service.generate_chat_response_with_tools", side_effect=fake):
            r = self.o.post("/api/users/ai-advisor/ask/", {"question": "Выручка?"}, format="json")
            self.assertEqual(r.status_code, 200)
            self.assertIn("1 250", r.data["answer"])
            self.assertEqual(calls, ["AIzaMAIN_" + "y" * 30, GOOD])
            # основной ключ на минуту пропускается
            self.o.post("/api/users/ai-advisor/ask/", {"question": "ещё"}, format="json")
            self.assertEqual(calls[-1], GOOD)
            r = self.o.post("/api/users/ai-advisor/ask/", {"question": "и ещё"}, format="json")
            self.assertEqual(r.status_code, 429)
            self.assertEqual(r.data["code"], "limit")

    def test_ask_all_keys_fail_503(self):
        self.o.put("/api/users/ai-advisor/settings/", {"main_key": GOOD}, format="json")
        with mock.patch("apps.main.telegram_bot.services.ai_service.generate_chat_response_with_tools", side_effect=ValueError("Gemini error (400): API key not valid")):
            r = self.o.post("/api/users/ai-advisor/ask/", {"question": "x"}, format="json")
        self.assertEqual(r.status_code, 503)

    def test_allowed_user_sees_only_what_owner_opened(self):
        self.o.put("/api/users/ai-advisor/settings/", {"main_key": GOOD, "allowed_user_ids": [str(self.a.pk)]}, format="json")
        seen = {}

        def fake_exec(company, name, args, ctx=None):
            return {"rows": [{"name": "Айбек", "phone": "+996700", "salary": "30000", "gross_profit": "5", "sales": "9"}]}

        def fake(api_key, **kw):
            seen["tools"] = {t["name"] for t in kw["tools"]}
            seen["blocked"] = kw["execute_tool_fn"]("get_salary", {})
            seen["row"] = kw["execute_tool_fn"]("get_client", {})["rows"][0]
            return "ok", "m", []

        p1 = mock.patch("apps.main.telegram_bot.services.ai_service.generate_chat_response_with_tools", side_effect=fake)
        p2 = mock.patch("apps.main.telegram_bot.services.ai_analytics_functions.execute_ai_function", side_effect=fake_exec)
        with p1, p2:
            self.assertEqual(self.as_user(self.a).post("/api/users/ai-advisor/ask/", {"question": "x"}, format="json").status_code, 200)
            self.assertNotIn("get_salary", seen["tools"]); self.assertNotIn("get_pnl", seen["tools"])
            self.assertIn("error", seen["blocked"])
            self.assertEqual(seen["row"], {"name": "Айбек", "sales": "9"})
            # владелец видит всё
            self.o.post("/api/users/ai-advisor/ask/", {"question": "x"}, format="json")
            self.assertIn("get_salary", seen["tools"]); self.assertIn("phone", seen["row"])
            # владелец открыл телефоны
            r = self.o.put("/api/users/ai-advisor/settings/", {"visible": {"phones": True}}, format="json")
            self.assertEqual(r.data["visible"], {"salary": False, "money": False, "phones": True})
            self.as_user(self.a).post("/api/users/ai-advisor/ask/", {"question": "x"}, format="json")
            self.assertEqual(seen["row"], {"name": "Айбек", "phone": "+996700", "sales": "9"})

    def test_style_validation(self):
        self.assertEqual(self.o.put("/api/users/ai-advisor/settings/", {"length": "huge"}, format="json").status_code, 400)
        r = self.o.put("/api/users/ai-advisor/settings/", {"length": "short", "tone": "business", "extra": "Говори про маржу"}, format="json")
        self.assertEqual((r.data["length"], r.data["tone"], r.data["extra"]), ("short", "business", "Говори про маржу"))

    def test_voice_transcribes_answers_and_speaks(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        self.o.put("/api/users/ai-advisor/settings/", {"main_key": GOOD}, format="json")
        wav = SimpleUploadedFile("q.wav", b"RIFF" + b"\x00" * 200, content_type="audio/wav")
        with mock.patch("apps.main.telegram_bot.services.ai_service.transcribe_voice", return_value="Сколько продал?") as tr, \
             mock.patch("apps.main.telegram_bot.services.ai_service.generate_chat_response_with_tools", return_value=("**100 сом**", "m", [])), \
             mock.patch("apps.main.telegram_bot.services.ai_service.synthesize_voice", return_value=b"OggS-audio"):
            r = self.o.post("/api/users/ai-advisor/ask-voice/", {"audio": wav, "speak": "1", "lang": "ru"}, format="multipart")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["question"], "Сколько продал?")
        self.assertIn("100", r.data["answer"])
        self.assertTrue(r.data["audio"])
        self.assertEqual(tr.call_args.kwargs["mime_type"], "audio/wav")

    def test_voice_not_heard_and_forbidden(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        self.o.put("/api/users/ai-advisor/settings/", {"main_key": GOOD}, format="json")
        with mock.patch("apps.main.telegram_bot.services.ai_service.transcribe_voice", return_value=""):
            r = self.o.post("/api/users/ai-advisor/ask-voice/", {"audio": SimpleUploadedFile("q.wav", b"RIFF0000", content_type="audio/wav")}, format="multipart")
        self.assertEqual(r.status_code, 422)
        r = self.as_user(self.c).post("/api/users/ai-advisor/ask-voice/", {"audio": SimpleUploadedFile("q.wav", b"RIFF", content_type="audio/wav")}, format="multipart")
        self.assertEqual(r.status_code, 403)

    def test_invoice_parse_then_apply(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        from apps.main.models import Product
        self.o.put("/api/users/ai-advisor/settings/", {"main_key": GOOD}, format="json")
        cola = Product.objects.create(company=self.company, name="Кола 1л", barcode="4870001", price=100, purchase_price=70, quantity=5)
        ai = {"rows": [{"name": "Кола 1л", "qty": 10, "unit_price": 75, "barcode": "4870001"},
                       {"name": "Сок яблочный", "qty": 4, "unit_price": None, "line_total": 400}], "unparsed": ["???"]}
        with mock.patch("apps.main.telegram_bot.services.ai_service.generate_json", return_value=ai):
            r = self.o.post("/api/users/ai-advisor/invoice/parse/",
                            {"file": SimpleUploadedFile("n.jpg", b"\xff\xd8x", content_type="image/jpeg")}, format="multipart")
        self.assertEqual(r.status_code, 200, r.data)
        rows = r.data["rows"]
        self.assertEqual(rows[0]["product_id"], str(cola.pk))
        self.assertIsNone(rows[1]["product_id"]); self.assertEqual(rows[1]["purchase_price"], "100.00")
        self.assertIn("???", r.data["unparsed"])
        # человек поправил цену нового товара
        rows[1]["price"] = "150"
        r = self.o.post("/api/users/ai-advisor/invoice/apply/", {"rows": rows}, format="json")
        self.assertEqual(r.data, {"done": 2, "failed": []})
        cola.refresh_from_db()
        self.assertEqual(cola.quantity, 15); self.assertEqual(cola.purchase_price, 75)
        juice = Product.objects.get(company=self.company, name="Сок яблочный")
        self.assertEqual((juice.quantity, juice.price), (4, 150))

    def test_invoice_needs_stock_right(self):
        self.o.put("/api/users/ai-advisor/settings/", {"main_key": GOOD, "allowed_user_ids": [str(self.b.pk)]}, format="json")
        u = self.as_user(self.b)
        self.assertEqual(u.post("/api/users/ai-advisor/invoice/parse/", {"text": "x"}, format="json").status_code, 403)
        self.assertEqual(u.post("/api/users/ai-advisor/invoice/apply/", {"rows": [{"name": "x", "qty": 1}]}, format="json").status_code, 403)

    def test_invoice_create_only_for_supplier_receipt(self):
        from apps.main.models import Product
        cola = Product.objects.create(company=self.company, name="Кола 1л", barcode="4870001", price=100, purchase_price=70, quantity=5)
        rows = [{"product_id": str(cola.pk), "name": "Кола 1л", "qty": "3", "purchase_price": "75", "price": ""},
                {"product_id": None, "name": "Сок", "barcode": "123", "qty": "2", "purchase_price": "50", "price": "70"}]
        r = self.o.post("/api/users/ai-advisor/invoice/apply/", {"rows": rows, "create_only": True}, format="json")
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data["ids"][0], str(cola.pk))
        juice = Product.objects.get(pk=r.data["ids"][1])
        self.assertEqual((juice.quantity, juice.price, juice.barcode), (0, 70, "123"))
        cola.refresh_from_db(); self.assertEqual(cola.quantity, 5)  # остаток даст приход поставщика
