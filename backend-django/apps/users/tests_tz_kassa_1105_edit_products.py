"""ТЗ кассы 05.11 п.12: can_edit_products в профиле и проверка сервером."""
import uuid
from decimal import Decimal

from django.test import TestCase
from rest_framework.test import APIClient

from apps.main.models import Product
from apps.users.models import Company, User


class EditProducts1105Tests(TestCase):
    def setUp(self):
        owner = User.objects.create_user(email=f"o-{uuid.uuid4().hex}@t.com", password="x", role="owner")
        self.company = Company.objects.create(name="A", owner=owner)
        owner.company = self.company
        owner.save()
        self.u = User.objects.create_user(email=f"c-{uuid.uuid4().hex}@t.com", password="x", company=self.company,
                                          role="manager", can_view_products=True, can_edit_products=False)
        self.api = APIClient()
        self.api.force_authenticate(self.u)
        self.p = Product.objects.create(company=self.company, name="Т", price=Decimal("10"), quantity=Decimal("1"))

    def test_profile_has_flag(self):
        r = self.api.get("/api/users/profile/")
        self.assertEqual(r.status_code, 200)
        self.assertIs(r.data["can_edit_products"], False)

    def test_writes_forbidden(self):
        H = {"HTTP_X_NURMARKET_CLIENT": "mobile/1.0.0"}
        for method, url, body in (
            ("patch", f"/api/main/products/{self.p.id}/", {"name": "X"}),
            ("post", f"/api/main/products/{self.p.id}/variants/", {"size": "M"}),
            ("post", f"/api/main/products/{self.p.id}/move-to-raw/", {}),
            ("post", f"/api/main/products/{self.p.id}/archive/", {}),
        ):
            r = getattr(self.api, method)(url, body, format="json", **H)
            self.assertEqual(r.status_code, 403, (url, getattr(r, "data", None)))
