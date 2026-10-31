from datetime import timedelta
from unittest import mock

from django.contrib.auth import get_user_model
from django.core import mail
from django.core.cache import cache
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from apps.users.password_reset import make_token


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend", DEFAULT_FROM_EMAIL="noreply@nurcrm.kg",
                   CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}})
class PasswordResetLinkTests(TestCase):
    def setUp(self):
        cache.clear()
        self.c = APIClient()
        self.user = get_user_model().objects.create_user(email="owner@shop.kg", password="OldPass123!")

    def request(self, email="owner@shop.kg", origin=None):
        headers = {"HTTP_ORIGIN": origin} if origin else {}
        return self.c.post("/api/users/password-reset/request/", {"email": email}, format="json", **headers)

    def token_from_mail(self):
        body = mail.outbox[-1].body
        return body.split("token=")[1].split()[0]

    def test_sends_link_to_known_email_with_allowed_origin(self):
        r = self.request(origin="https://front-market.vercel.app")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("https://front-market.vercel.app/reset-password?token=", mail.outbox[0].body)
        self.assertEqual(mail.outbox[0].to, ["owner@shop.kg"])

    def test_unknown_origin_falls_back_to_market(self):
        self.request(origin="https://evil.example")
        self.assertIn("https://market.nurcrm.kg/reset-password?token=", mail.outbox[0].body)

    def test_unknown_email_same_answer_no_mail(self):
        r = self.request(email="nobody@shop.kg")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(mail.outbox), 0)

    def test_bad_email_400(self):
        self.assertEqual(self.request(email="not-an-email").status_code, 400)

    def test_confirm_sets_password_and_link_is_one_time(self):
        self.request()
        token = self.token_from_mail()
        r = self.c.post("/api/users/password-reset/check/", {"token": token}, format="json")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["email"], "ow***@shop.kg")
        r = self.c.post("/api/users/password-reset/confirm/", {"token": token, "password": "NewPass456!"}, format="json")
        self.assertEqual(r.status_code, 200)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("NewPass456!"))
        again = self.c.post("/api/users/password-reset/confirm/", {"token": token, "password": "Another789!"}, format="json")
        self.assertEqual(again.status_code, 400)
        self.assertEqual(again.data["code"], "invalid_token")

    def test_expires_after_15_minutes(self):
        token = make_token(self.user)
        import time
        real = time.time
        with mock.patch("django.core.signing.time.time", lambda: real() + 15 * 60 + 5):
            r = self.c.post("/api/users/password-reset/check/", {"token": token}, format="json")
        self.assertEqual(r.status_code, 400)

    def test_short_password_rejected(self):
        token = make_token(self.user)
        r = self.c.post("/api/users/password-reset/confirm/", {"token": token, "password": "123"}, format="json")
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.data["code"], "validation_error")

    def test_tampered_token_rejected(self):
        token = make_token(self.user)
        r = self.c.post("/api/users/password-reset/check/", {"token": token[:-2] + "xx"}, format="json")
        self.assertEqual(r.status_code, 400)

    def test_rate_limit_per_email(self):
        codes = [self.request().status_code for _ in range(4)]
        self.assertEqual(codes[:3], [200, 200, 200])
        self.assertEqual(codes[3], 429)

    def test_mail_failure_still_200(self):
        with mock.patch("apps.users.password_reset._send", side_effect=OSError("smtp down")):
            self.assertEqual(self.request().status_code, 200)

    def test_falls_back_to_second_mailbox(self):
        from apps.users import password_reset as pr
        sent = []

        class Boom:
            def send_messages(self, msgs):
                raise OSError("primary down")

        class Ok:
            def send_messages(self, msgs):
                sent.extend(msgs)
                return len(msgs)

        with mock.patch.object(pr, "_mail_routes", return_value=[(Boom(), "nurcrm2025@gmail.com"), (Ok(), "nurcrm.youtube@gmail.com")]):
            self.assertEqual(self.request().status_code, 200)
        self.assertEqual(len(sent), 1)
        self.assertEqual(sent[0].from_email, "nurcrm.youtube@gmail.com")

    def test_routes_include_fallback_only_when_configured(self):
        from apps.users import password_reset as pr
        with mock.patch.dict("os.environ", {"EMAIL_FALLBACK_HOST_USER": "", "EMAIL_FALLBACK_HOST_PASSWORD": ""}):
            self.assertEqual(len(pr._mail_routes()), 1)
        with mock.patch.dict("os.environ", {"EMAIL_FALLBACK_HOST_USER": "nurcrm.youtube@gmail.com", "EMAIL_FALLBACK_HOST_PASSWORD": "abcd efgh ijkl mnop"}):
            routes = pr._mail_routes()
        self.assertEqual(len(routes), 2)
        self.assertEqual(routes[1][1], "nurcrm.youtube@gmail.com")
        self.assertEqual(routes[1][0].password, "abcdefghijklmnop")
