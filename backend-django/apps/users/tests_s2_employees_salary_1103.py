"""S2 (аудит 03.11): GET users/employees/ — и с правом «Зарплата» (can_view_salary)."""
import uuid

from django.test import override_settings

from apps.users.models import User
from apps.users.tests_tz_n16_permissions import LOCMEM, N16Base

NEW = "kassa/1.17.61"  # новый клиент: права Н-16 действуют


@override_settings(CACHES=LOCMEM)
class EmployeesListSalaryTests(N16Base):
    def get(self, user):
        api = self.api_for(user)
        return api.get("/api/users/employees/", HTTP_X_NURMARKET_CLIENT=NEW)

    def test_salary_flag_opens_list(self):
        r = self.get(self.cashier)
        self.assertEqual(r.status_code, 403, r.content)
        acc = User.objects.create_user(email=f"z{uuid.uuid4().hex[:6]}@t.kg", password="x",
                                       company=self.company, role=None, can_view_salary=True)
        r = self.get(acc)
        self.assertEqual(r.status_code, 200, r.content)
        self.assertTrue(any(x["id"] == str(self.cashier.id) for x in r.json()["results"]))

    def test_salary_flag_does_not_open_edit(self):
        acc = User.objects.create_user(email=f"z{uuid.uuid4().hex[:6]}@t.kg", password="x",
                                       company=self.company, role=None, can_view_salary=True)
        r = self.api_for(acc).patch(f"/api/users/employees/{self.cashier.id}/", {"first_name": "X"}, format="json",
                                    HTTP_X_NURMARKET_CLIENT=NEW)
        self.assertEqual(r.status_code, 403, r.content)
