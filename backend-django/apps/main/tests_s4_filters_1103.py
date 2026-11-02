"""S4 (аудит 03.11): construction/shifts/?date_from=&date_to=; pos/cart-item-deletions/ — даты, user, search."""
import uuid
from datetime import timedelta
from decimal import Decimal

from django.test import override_settings
from django.utils import timezone

from apps.construction.models import CashShift
from apps.main.models import CartItemDeletionLog
from apps.users.models import User
from apps.users.tests_tz_n16_permissions import LOCMEM, N16Base


@override_settings(CACHES=LOCMEM)
class S4FiltersTests(N16Base):
    def test_shifts_by_opened_date(self):
        old = self.open_shift(self.cashier)
        CashShift.objects.filter(pk=old.pk).update(opened_at=timezone.now() - timedelta(days=10),
                                                   status=CashShift.Status.CLOSED)
        new = self.open_shift(self.owner)
        today = timezone.localdate().isoformat()
        ago = (timezone.localdate() - timedelta(days=10)).isoformat()
        ids = lambda q: {x["id"] for x in self.api_owner.get("/api/construction/shifts/" + q).json()["results"]}
        self.assertEqual(ids(f"?date_from={today}"), {str(new.id)})
        self.assertEqual(ids(f"?date_from={ago}&date_to={ago}"), {str(old.id)})
        self.assertEqual(ids(""), {str(new.id), str(old.id)})
        self.assertEqual(self.api_owner.get("/api/construction/shifts/?date_from=xx").status_code, 400)

    def test_cart_item_deletions_filters(self):
        other = User.objects.create_user(email=f"d{uuid.uuid4().hex[:6]}@t.kg", password="x", company=self.company)
        a = CartItemDeletionLog.objects.create(company=self.company, product=self.product, product_name="Хлеб",
                                               quantity=Decimal("1"), deleted_by=self.cashier)
        b = CartItemDeletionLog.objects.create(company=self.company, product_name="Молоко", quantity=Decimal("2"),
                                               deleted_by=other)
        CartItemDeletionLog.objects.filter(pk=b.pk).update(created_at=timezone.now() - timedelta(days=5))

        def ids(q):
            r = self.api_owner.get("/api/main/pos/cart-item-deletions/" + q)
            self.assertEqual(r.status_code, 200, r.content)
            data = r.json()
            rows = data["results"] if isinstance(data, dict) else data
            return {x["id"] for x in rows}

        self.assertEqual(ids(""), {str(a.id), str(b.id)})
        self.assertEqual(ids(f"?user={other.id}"), {str(b.id)})
        self.assertEqual(ids("?search=Хлеб"), {str(a.id)})
        self.assertEqual(ids(f"?search={self.product.barcode}"), {str(a.id)})
        self.assertEqual(ids(f"?date_from={timezone.localdate().isoformat()}"), {str(a.id)})
        self.assertEqual(self.api_owner.get("/api/main/pos/cart-item-deletions/?user=zz").status_code, 400)
