"""ТЗ кассы 05.11 п.11: company/addons/ читают все сотрудники компании."""
import uuid

from django.test import TestCase
from rest_framework.test import APIClient

from apps.users.models import Company, User


class Addons1105Tests(TestCase):
    def test_cashier_and_manager_read_addons(self):
        owner = User.objects.create_user(email=f"o-{uuid.uuid4().hex}@t.com", password="x", role="owner")
        company = Company.objects.create(name="A", owner=owner)
        owner.company = company
        owner.save()
        for role in ("cashier", "manager", "seller"):
            u = User.objects.create_user(email=f"{role}-{uuid.uuid4().hex}@t.com", password="x", company=company, role=role)
            api = APIClient()
            api.force_authenticate(u)
            for hdr in ({}, {"HTTP_X_NURMARKET_CLIENT": "kassa/1.17.70"}, {"HTTP_X_NURMARKET_CLIENT": "mobile/1.2.0"}):
                r = api.get("/api/users/company/addons/", **hdr)
                self.assertEqual(r.status_code, 200, (role, hdr, getattr(r, "data", None)))
                self.assertIsInstance(r.data, list)
