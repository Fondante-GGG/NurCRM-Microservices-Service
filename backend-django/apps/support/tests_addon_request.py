from unittest import mock
from urllib.parse import parse_qs, urlparse

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from apps.users.models import Company, CompanyAddon

User = get_user_model()


@override_settings(CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}},
                   ADDON_REQUEST_TELEGRAM_BOT_TOKEN="t", ADDON_REQUEST_TELEGRAM_CHAT_ID="-1")
class AddonRequestFlowTests(TestCase):
    def setUp(self):
        cache.clear()
        self.owner = User.objects.create_user(email="o@shop.test", password="p12345678", role="owner")
        self.company = Company.objects.create(name="Shop", slug="shop-x", owner=self.owner)
        self.owner.company = self.company; self.owner.owned_company = self.company; self.owner.save()
        self.c = APIClient(); self.c.force_authenticate(self.owner)

    def send(self, item="kassa-loyalty"):
        sent = {}
        def fake(token, chat, text):
            sent["text"] = text
            return True
        with mock.patch("apps.support.addon_request._send_raw", side_effect=fake):
            r = self.c.post("/api/support/addon-requests/", {"item": item, "title": "Лояльность", "phone": "+996555123456"}, format="json")
        return r, sent.get("text", "")

    def link_token(self, text):
        url = text.split('href="')[1].split('"')[0]
        return parse_qs(urlparse(url).query)["t"][0]

    def test_request_saved_as_sent_and_has_enable_link(self):
        r, text = self.send()
        self.assertEqual(r.status_code, 201)
        self.assertIn("/support/addon-requests/approve/?t=", text)
        st = self.c.get("/api/support/addon-requests/").data["requests"]
        self.assertEqual([(x["item"], x["status"]) for x in st], [("kassa-loyalty", "sent")])

    def test_get_does_not_enable_post_enables_and_marks(self):
        _, text = self.send()
        t = self.link_token(text)
        anon = APIClient()
        page = anon.get("/api/support/addon-requests/approve/", {"t": t})
        self.assertEqual(page.status_code, 200)
        self.assertFalse(CompanyAddon.objects.filter(company=self.company).exists())
        done = anon.post("/api/support/addon-requests/approve/", {"t": t, "period": "month"})
        self.assertEqual(done.status_code, 200)
        a = CompanyAddon.objects.get(company=self.company, code="kassa-loyalty")
        self.assertTrue(a.is_effective()); self.assertIsNotNone(a.until)
        st = self.c.get("/api/support/addon-requests/").data["requests"]
        self.assertEqual(st[0]["status"], "enabled")
        codes = [x["code"] for x in self.c.get("/api/users/company/addons/").data if x["active"]]
        self.assertIn("kassa-loyalty", codes)

    def test_forever_and_bad_token(self):
        _, text = self.send("kassa-scales")
        t = self.link_token(text)
        APIClient().post("/api/support/addon-requests/approve/", {"t": t, "period": "forever"})
        self.assertIsNone(CompanyAddon.objects.get(company=self.company, code="kassa-scales").until)
        self.assertEqual(APIClient().post("/api/support/addon-requests/approve/", {"t": t + "x"}).status_code, 400)

    def test_constructor_has_no_enable_link(self):
        _, text = self.send("constructor")
        self.assertNotIn("approve/?t=", text)
