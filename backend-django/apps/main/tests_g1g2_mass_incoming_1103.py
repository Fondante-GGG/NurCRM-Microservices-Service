"""G1/G2 (аудит 03.11): mass-incoming — закупочная новой карточки сохраняется всегда; branch для новых карточек."""
import uuid
from decimal import Decimal

from django.test import TestCase
from rest_framework.test import APIClient

from apps.main.models import Branch, Product
from apps.users.models import BranchMembership, Company, User

URL = "/api/main/products/mass-incoming/"


class MassIncomingG1G2Tests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(email=f"mi-{uuid.uuid4().hex}@t.com", password="x", role="owner")
        self.company = Company.objects.create(name="MI", owner=self.user)
        self.user.company = self.company
        self.user.save()
        self.br = Branch.objects.create(company=self.company, name="Филиал 1")
        self.br2 = Branch.objects.create(company=self.company, name="Филиал 2")
        other_owner = User.objects.create_user(email=f"mo-{uuid.uuid4().hex}@t.com", password="x")
        self.other_br = Branch.objects.create(company=Company.objects.create(name="O", owner=other_owner), name="Чужой")
        self.api = APIClient()
        self.api.force_authenticate(self.user)

    def row(self, bc, **kw):
        return {"barcode": bc, "name": f"Товар {bc}", "quantity": "2", "from_global": False, **kw}

    def post(self, items, url=URL, **kw):
        return self.api.post(url, {"items": items, **kw}, format="json", HTTP_IDEMPOTENCY_KEY=str(uuid.uuid4()))

    def test_g1_purchase_price_saved_with_explicit_price(self):
        r = self.post([self.row("2000000000011", price="150.00", purchase_price="100.00")])
        self.assertEqual(r.status_code, 201, r.content)
        p = Product.objects.get(company=self.company, barcode="2000000000011")
        self.assertEqual(p.purchase_price, Decimal("100.00"))
        self.assertEqual(p.price, Decimal("150.00"))
        self.assertEqual(Decimal(str(p.markup_percent)).quantize(Decimal("0.01")), Decimal("50.00"))
        self.assertEqual(r.json()["items"][0]["purchase_price"], "100.00")

    def test_g1_without_purchase_as_before(self):
        r = self.post([self.row("2000000000028", price="80.00")])
        self.assertEqual(r.status_code, 201, r.content)
        p = Product.objects.get(company=self.company, barcode="2000000000028")
        self.assertEqual(p.purchase_price, Decimal("0"))

    def test_g2_branch_in_body_and_query(self):
        r = self.post([self.row("2000000000035", price="10")], branch=str(self.br.id))
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(Product.objects.get(barcode="2000000000035").branch_id, self.br.id)
        r = self.post([self.row("2000000000042", price="10")], url=f"{URL}?branch={self.br2.id}")
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(Product.objects.get(barcode="2000000000042").branch_id, self.br2.id)

    def test_g2_without_branch_company_catalog(self):
        r = self.post([self.row("2000000000059", price="10")])
        self.assertEqual(r.status_code, 201, r.content)
        self.assertIsNone(Product.objects.get(barcode="2000000000059").branch_id)
        r = self.post([self.row("2000000000066", price="10")], branch="main")
        self.assertIsNone(Product.objects.get(barcode="2000000000066").branch_id)

    def test_g2_foreign_or_bad_branch(self):
        r = self.post([self.row("2000000000073", price="10")], branch=str(self.other_br.id))
        self.assertEqual(r.status_code, 404, r.content)
        self.assertEqual(r.json()["code"], "branch_not_found")
        r = self.post([self.row("2000000000073", price="10")], branch="xx")
        self.assertEqual(r.status_code, 400, r.content)
        self.assertFalse(Product.objects.filter(barcode="2000000000073").exists())

    def test_g2_employee_other_branch_forbidden(self):
        emp = User.objects.create_user(email=f"e-{uuid.uuid4().hex}@t.com", password="x", company=self.company)
        BranchMembership.objects.create(user=emp, branch=self.br, is_primary=True)
        api = APIClient()
        api.force_authenticate(emp)
        r = api.post(URL, {"items": [self.row("2000000000080", price="10")], "branch": str(self.br2.id)},
                     format="json")
        self.assertEqual(r.status_code, 403, r.content)
        r = api.post(URL, {"items": [self.row("2000000000080", price="10")], "branch": str(self.br.id)},
                     format="json")
        self.assertEqual(r.status_code, 201, r.content)
