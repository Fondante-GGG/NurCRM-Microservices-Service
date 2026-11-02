"""S5 (аудит 03.11): rentals/?branch=<uuid>|main."""
from datetime import date

from django.test import override_settings

from apps.main.models import Branch, Rental
from apps.users.tests_tz_n16_permissions import LOCMEM, N16Base


@override_settings(CACHES=LOCMEM)
class RentalsBranchTests(N16Base):
    def ids(self, q):
        r = self.api_owner.get("/api/rentals/" + q)
        self.assertEqual(r.status_code, 200, r.content)
        data = r.json()
        rows = data["results"] if isinstance(data, dict) else data
        return {x["id"] for x in rows}

    def test_branch_filter(self):
        br = Branch.objects.create(company=self.company, name="Филиал")
        mk = lambda n, b: Rental.objects.create(company=self.company, number=n, client=self.client_obj, branch=b,
                                                 date_from=date(2026, 11, 1), date_to=date(2026, 11, 5))
        r1, r2 = mk(1, br), mk(2, None)
        self.assertEqual(self.ids(f"?branch={br.id}"), {str(r1.id)})
        self.assertEqual(self.ids("?branch=main"), {str(r2.id)})
        self.assertEqual(self.ids(""), {str(r1.id), str(r2.id)})
        self.assertEqual(self.api_owner.get("/api/rentals/?branch=xx").status_code, 400)
