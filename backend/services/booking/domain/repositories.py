from typing import Optional, List, Protocol
import uuid
from backend.services.booking.domain.models import BookingRequest


class BookingRequestRepository(Protocol):
    def get_by_id(self, company_id: uuid.UUID, booking_id: uuid.UUID) -> Optional[BookingRequest]:
        ...

    def list_by_company(self, company_id: uuid.UUID, status: Optional[str] = None) -> List[BookingRequest]:
        ...

    def save(self, booking: BookingRequest) -> None:
        ...

    def delete(self, company_id: uuid.UUID, booking_id: uuid.UUID) -> None:
        ...
