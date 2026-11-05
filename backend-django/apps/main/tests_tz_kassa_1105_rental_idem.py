"""ТЗ кассы 05.11 п.8: создание проката с Idempotency-Key."""
from datetime import timedelta

from django.utils import timezone

from apps.main.models import ProductVariant
from apps.main.rentals import Rental
from apps.main.tests_tz_n21_rentals import RentalN21Tests


class RentalIdem1105Tests(RentalN21Tests):
    def test_create_replay(self):
        today = timezone.localdate()
        body = {"client": str(self.client_obj.id), "items": [{"variant": str(self.m.id)}],
                "date_from": today.isoformat(), "date_to": (today + timedelta(days=2)).isoformat(),
                "tariff": "сутки", "deposit_type": "money", "deposit_amount": "500.00"}
        r1 = self.api.post("/api/rentals/", body, format="json", HTTP_IDEMPOTENCY_KEY="rent-1")
        r2 = self.api.post("/api/rentals/", body, format="json", HTTP_IDEMPOTENCY_KEY="rent-1")
        self.assertEqual(r1.status_code, 201, r1.data)
        self.assertFalse(r1.data["replayed"])
        self.assertEqual(r2.status_code, 201)
        self.assertTrue(r2.data["replayed"])
        self.assertEqual(r1.data["id"], r2.data["id"])
        self.assertEqual(Rental.objects.filter(company=self.company).count(), 1)
        self.assertEqual(ProductVariant.objects.get(pk=self.m.pk).quantity, 4)
