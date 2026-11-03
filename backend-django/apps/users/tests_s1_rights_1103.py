"""S1 (аудит 03.11): сотрудник не может сделать себя админом; роль admin и опасные права — только владелец/админ."""
import uuid

from django.test import override_settings

from apps.users.models import User
from apps.users.tests_tz_n16_permissions import LOCMEM, N16Base


@override_settings(CACHES=LOCMEM)
class SelfRightsTests(N16Base):
    def setUp(self):
        super().setUp()
        # как на бою: у большинства сотрудников role пустая, у части есть «Сотрудники»
        self.hr = User.objects.create_user(
            email=f"h{uuid.uuid4().hex[:6]}@t.kg", password="x", company=self.company, role=None,
            can_view_employees=True, can_view_dashboard=True,
        )
        self.api_hr = self.api_for(self.hr)
        self.rop = User.objects.create_user(
            email=f"r{uuid.uuid4().hex[:6]}@t.kg", password="x", company=self.company, role="rop",
            can_view_employees=True,
        )
        self.api_rop = self.api_for(self.rop)

    def fresh(self, u):
        return User.objects.get(pk=u.pk)

    def assertForbidden(self, r):
        self.assertEqual(r.status_code, 403, r.content)
        self.assertEqual(r.json().get("code"), "permission_denied", r.content)

    # --- профиль: себе ---
    def test_cannot_make_self_admin(self):
        for api, u in ((self.api_hr, self.hr), (self.api_cashier, self.cashier), (self.api_rop, self.rop)):
            self.assertForbidden(api.patch("/api/users/profile/", {"role": "admin"}, format="json"))
            self.assertForbidden(api.patch("/api/users/profile/", {"role": "owner"}, format="json"))
        self.assertIsNone(self.fresh(self.hr).role)
        self.assertEqual(self.fresh(self.cashier).role, "salesperson")

    def test_cannot_grant_self_flags(self):
        for body in ({"can_view_settings": True}, {"can_view_employees": True}, {"can_use_pos": False},
                     {"can_edit_employees": False}, {"can_post_negative_stock": True},
                     {"can_edit_purchase_documents": True}, {"can_cash_negative": True}):
            self.assertForbidden(self.api_cashier.patch("/api/users/profile/", body, format="json"))
        u = self.fresh(self.cashier)
        self.assertFalse(u.can_view_settings)
        self.assertIsNone(u.can_post_negative_stock)

    def test_admin_cannot_change_own_role_or_flags(self):
        self.assertForbidden(self.api_admin.patch("/api/users/profile/", {"role": "owner"}, format="json"))
        self.assertForbidden(self.api_admin.patch("/api/users/profile/", {"can_post_closed_period": True}, format="json"))

    def test_full_card_unchanged_passes(self):
        """Клиенты шлют профиль целиком — без реальных изменений прав это не ошибка."""
        card = self.api_cashier.get("/api/users/profile/").json()
        body = {k: v for k, v in card.items() if k.startswith("can_") or k in ("role", "first_name")}
        body["first_name"] = "Новое"
        body.pop("can_view_showcase", None)
        r = self.api_cashier.patch("/api/users/profile/", body, format="json")
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(self.fresh(self.cashier).first_name, "Новое")
        # NULL и false у can_view_* — одно и то же
        r = self.api_hr.patch("/api/users/profile/", {"can_view_cashbox": False, "language": "ky"}, format="json")
        self.assertEqual(r.status_code, 200, r.content)

    def test_owner_keeps_self_flags_but_not_role(self):
        r = self.api_owner.patch("/api/users/profile/", {"can_view_building_stock": True}, format="json")
        self.assertEqual(r.status_code, 200, r.content)  # старый сайт так дописывает права сферы
        self.assertForbidden(self.api_owner.patch("/api/users/profile/", {"role": "admin"}, format="json"))
        self.assertEqual(self.fresh(self.owner).role, "owner")

    def test_profile_other_fields_still_work(self):
        r = self.api_cashier.patch("/api/users/profile/", {"language": "ky", "phone_number": "+996700000001"}, format="json")
        self.assertEqual(r.status_code, 200, r.content)

    # --- чужая карточка ---
    def emp(self, u):
        return f"/api/users/employees/{u.id}/"

    def test_hr_flag_alone_cannot_edit_employees(self):
        r = self.api_hr.patch(self.emp(self.cashier), {"role": "admin"}, format="json")
        self.assertEqual(r.status_code, 403, r.content)
        self.assertEqual(self.fresh(self.cashier).role, "salesperson")

    def test_rop_cannot_give_admin_or_touch_admin(self):
        self.assertForbidden(self.api_rop.patch(self.emp(self.cashier), {"role": "admin"}, format="json"))
        self.assertForbidden(self.api_rop.patch(self.emp(self.cashier), {"role": "owner"}, format="json"))
        self.assertForbidden(self.api_rop.patch(self.emp(self.admin), {"can_view_settings": False}, format="json"))
        self.assertForbidden(self.api_rop.patch(self.emp(self.admin), {"role": "salesperson"}, format="json"))
        self.assertForbidden(self.api_rop.patch(self.emp(self.cashier), {"can_post_negative_stock": True}, format="json"))
        self.assertEqual(self.fresh(self.admin).role, "admin")
        # обычные правки РОП — как раньше
        r = self.api_rop.patch(self.emp(self.cashier), {"can_view_clients": True, "phone_number": "+996700000002"}, format="json")
        self.assertEqual(r.status_code, 200, r.content)

    def test_rop_cannot_create_admin(self):
        r = self.api_rop.post("/api/users/employees/create/", {"email": "newadm@t.kg", "role": "admin", "first_name": "А", "last_name": "Б"}, format="json")
        self.assertForbidden(r)
        self.assertFalse(User.objects.filter(email="newadm@t.kg").exists())

    def test_admin_can_give_admin_and_danger_but_not_owner(self):
        r = self.api_admin.patch(self.emp(self.cashier), {"role": "admin"}, format="json")
        self.assertEqual(r.status_code, 200, r.content)
        self.assertForbidden(self.api_admin.patch(self.emp(self.cashier), {"role": "owner"}, format="json"))
        r = self.api_admin.patch(self.emp(self.hr), {"can_post_negative_stock": True}, format="json")
        self.assertEqual(r.status_code, 200, r.content)
        self.assertTrue(self.fresh(self.hr).can_post_negative_stock)

    def test_owner_sets_danger_rights(self):
        r = self.api_owner.patch(self.emp(self.cashier), {"can_unpost_documents": True, "can_cash_negative": True}, format="json")
        self.assertEqual(r.status_code, 200, r.content)
        u = self.fresh(self.cashier)
        self.assertTrue(u.can_unpost_documents)
        self.assertTrue(u.can_cash_negative)
        r = self.api_owner.patch(self.emp(self.cashier), {"can_cash_negative": False}, format="json")
        self.assertEqual(r.status_code, 200, r.content)
        self.assertFalse(self.fresh(self.cashier).can_cash_negative)

    def test_full_card_does_not_turn_role_default_into_no(self):
        """front-market шлёт Boolean(null)=false по всем опасным правам при каждом сохранении:
        у админа (NULL = по умолчанию «можно» отменять проведение) это не должно записать явное «нет»."""
        other_admin = User.objects.create_user(email=f"a2{uuid.uuid4().hex[:6]}@t.kg", password="x",
                                               company=self.company, role="admin")
        card = {k: False for k in ("can_post_negative_stock", "can_unpost_documents", "can_change_document_date",
                                   "can_post_closed_period", "can_cash_negative")}
        r = self.api_owner.patch(self.emp(other_admin), {**card, "comment": "x"}, format="json")
        self.assertEqual(r.status_code, 200, r.content)
        self.assertIsNone(self.fresh(other_admin).can_unpost_documents)
        r = self.api_rop.patch(self.emp(self.cashier), {**card, "comment": "y"}, format="json")
        self.assertEqual(r.status_code, 200, r.content)  # у кассира и так «нет» — РОП может сохранить карточку
        # ранее выданное снимается явно
        User.objects.filter(pk=self.cashier.pk).update(can_cash_negative=True)
        self.assertForbidden(self.api_rop.patch(self.emp(self.cashier), {"can_cash_negative": False}, format="json"))
        r = self.api_owner.patch(self.emp(self.cashier), {"can_cash_negative": False}, format="json")
        self.assertEqual(r.status_code, 200, r.content)
        self.assertFalse(self.fresh(self.cashier).can_cash_negative)

    def test_list_shows_danger_rights(self):
        User.objects.filter(pk=self.cashier.pk).update(can_unpost_documents=True)
        rows = self.api_owner.get("/api/users/employees/").json()["results"]
        row = [x for x in rows if x["id"] == str(self.cashier.id)][0]
        self.assertIs(row["can_unpost_documents"], True)
        self.assertIsNone(row["can_cash_negative"])
