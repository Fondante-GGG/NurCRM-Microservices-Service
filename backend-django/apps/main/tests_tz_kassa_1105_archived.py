"""ТЗ кассы 05.11 п.13: products/list/?is_archived=true — только архив."""
import uuid
from decimal import Decimal

from django.test import TestCase
from rest_framework.test import APIClient

from apps.main.models import Product
from apps.users.models import Company, User


class Archived1105Tests(TestCase):
    def test_filter(self):
        o = User.objects.create_user(email=f"o-{uuid.uuid4().hex}@t.com", password="x", role="owner")
        c = Company.objects.create(name="A", owner=o)
        o.company = c
        o.save()
        api = APIClient()
        api.force_authenticate(o)
        a = Product.objects.create(company=c, name="Архив", price=Decimal("1"), status=Product.Status.ARCHIVED)
        Product.objects.create(company=c, name="Живой", price=Decimal("1"))

        def ids(q):
            d = api.get("/api/main/products/list/" + q).data
            return {x["id"] for x in (d.get("results") if isinstance(d, dict) else d)}
        self.assertEqual(ids("?is_archived=true"), {str(a.id)})
        self.assertEqual(ids("?status=archived"), {str(a.id)})
        self.assertNotIn(str(a.id), ids(""))
        self.assertEqual(len(ids("?include_archived=1")), 2)
