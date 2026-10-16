from typing import Optional, List
import uuid

from libs.common.domain import Money, Phone
from backend.services.booking.domain.models import BookingRequest
from backend.services.booking.domain.repositories import BookingRequestRepository
from backend.services.booking.infrastructure.models import BookingRequestModel


class DjangoBookingRequestRepository(BookingRequestRepository):
    def _to_domain(self, m: BookingRequestModel) -> BookingRequest:
        return BookingRequest(
            id=m.id,
            company_id=m.company_id,
            client_name=m.client_name,
            client_phone=Phone(m.client_phone),
            services=m.services,
            master_id=m.master_id,
            date=m.date,
            time_start=m.time_start,
            time_end=m.time_end,
            total_price=Money(m.total_price),
            total_duration_min=m.total_duration_min,
            payment_method=m.payment_method,
            client_comment=m.client_comment or "",
            status=m.status,
            appointment_id=m.appointment_id,
            confirmed_by=m.confirmed_by,
            version=m.version,
            created_at=m.created_at,
            updated_at=m.updated_at,
        )

    def get_by_id(self, company_id: uuid.UUID, booking_id: uuid.UUID, for_update: bool = False) -> Optional[BookingRequest]:
        try:
            qs = BookingRequestModel.objects.filter(company_id=company_id, id=booking_id)
            if for_update:
                qs = qs.select_for_update()
            m = qs.first()
            if not m:
                return None
            return self._to_domain(m)
        except BookingRequestModel.DoesNotExist:
            return None

    def list_by_company(self, company_id: uuid.UUID, status: Optional[str] = None) -> List[BookingRequest]:
        qs = BookingRequestModel.objects.filter(company_id=company_id)
        if status:
            qs = qs.filter(status=status)
        return [self._to_domain(m) for m in qs.order_by("-created_at")]

    def save(self, booking: BookingRequest) -> None:
        BookingRequestModel.objects.update_or_create(
            id=booking.id,
            company_id=booking.company_id,
            defaults={
                "client_name": booking.client_name,
                "client_phone": str(booking.client_phone),
                "services": booking.services,
                "master_id": booking.master_id,
                "date": booking.date,
                "time_start": booking.time_start,
                "time_end": booking.time_end,
                "total_price": booking.total_price.amount,
                "total_duration_min": booking.total_duration_min,
                "payment_method": booking.payment_method,
                "client_comment": booking.client_comment,
                "status": booking.status,
                "appointment_id": booking.appointment_id,
                "confirmed_by": booking.confirmed_by,
                "version": booking.version,
                "updated_at": booking.updated_at,
            },
        )

    def delete(self, company_id: uuid.UUID, booking_id: uuid.UUID) -> None:
        BookingRequestModel.objects.filter(company_id=company_id, id=booking_id).delete()
