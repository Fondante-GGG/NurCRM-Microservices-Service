"""S8 (аудит 03.11): users/ui-preferences/ — поле dark_style (= theme_dark_palette)."""
import uuid

from django.core.cache import cache
from django.test import TestCase
from rest_framework.test import APIClient

from apps.users.models import User, UserUiPreferences


class DarkStyleTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(email=f"d{uuid.uuid4().hex[:6]}@t.kg", password="x")
        self.api = APIClient()
        self.api.force_authenticate(self.user)

    def test_dark_style_roundtrip(self):
        r = self.api.patch("/api/users/ui-preferences/", {"dark_style": "classic"}, format="json")
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual((r.data["dark_style"], r.data["theme_dark_palette"]), ("classic", "classic"))
        self.assertEqual(UserUiPreferences.objects.get(user=self.user).theme_dark_palette, "classic")
        # старое имя тоже работает
        r = self.api.patch("/api/users/ui-preferences/", {"theme_dark_palette": "soft"}, format="json")
        self.assertEqual(self.api.get("/api/users/ui-preferences/").data["dark_style"], "soft")
        r = self.api.patch("/api/users/ui-preferences/", {"dark_style": "neon"}, format="json")
        self.assertEqual(r.status_code, 400)
