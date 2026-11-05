"""ТЗ кассы 05.11 п.19: GET main/pipelines/ не 500."""
import uuid

from django.test import TestCase
from rest_framework.test import APIClient

from apps.users.models import Company, User


class Pipelines1105Tests(TestCase):
    def test_list(self):
        o = User.objects.create_user(email=f"o-{uuid.uuid4().hex}@t.com", password="x", role="owner")
        c = Company.objects.create(name="A", owner=o)
        o.company = c
        o.save()
        api = APIClient()
        api.force_authenticate(o)
        r = api.get("/api/main/pipelines/")
        self.assertEqual(r.status_code, 200, getattr(r, "data", None))

    def test_other_lists(self):
        o = User.objects.create_user(email=f"o-{uuid.uuid4().hex}@t.com", password="x", role="owner")
        c = Company.objects.create(name="B", owner=o)
        o.company = c
        o.save()
        api = APIClient()
        api.force_authenticate(o)
        for u in ("/api/main/analytics/", "/api/main/integrations/"):
            self.assertEqual(api.get(u).status_code, 200, u)
