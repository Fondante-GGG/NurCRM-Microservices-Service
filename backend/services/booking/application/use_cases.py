from __future__ import annotations
import uuid
from decimal import Decimal
from datetime import datetime, timezone
from typing import Protocol, List, Optional, Dict, Any

from libs.common.domain import Money, Phone
from libs.common.events import EventEnvelope, EventTypes
from libs.common.exceptions import NotFoundError, SlotBusyError, AlreadyProcessedError, ConflictError
from backend.services.booking.domain.models import BookingRequest, BookingStatus
from backend.services.booking.domain.repositories import BookingRequestRepository
from backend.services.booking.application.dto import CreateBookingRequestDTO, BookingRequestDTO


class BookingUnitOfWork(Protocol):
    bookings: BookingRequestRepository

    def __enter__(self) -> "BookingUnitOfWork":
        ...

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        ...

    def commit(self) -> None:
        ...

    def record_outbox(self, event: EventEnvelope) -> None:
        ...


class ClientServiceClientPort(Protocol):
    def find_or_create_client(self, company_id: uuid.UUID, full_name: str, phone: str) -> Dict[str, Any]:
        ...


class ScheduleServiceClientPort(Protocol):
    def create_appointment(
        self,
        company_id: uuid.UUID,
        client_id: uuid.UUID,
        client_name: str,
        barber_id: uuid.UUID,
        service_ids: List[uuid.UUID],
        start_at: str,
        idempotency_key: str,
        comment: str = "",
    ) -> Dict[str, Any]:
        ...


class CreateBookingRequestUseCase:
    def __init__(self, uow: BookingUnitOfWork):
        self.uow = uow

    def execute(self, dto: CreateBookingRequestDTO) -> BookingRequestDTO:
        with self.uow:
            phone_vo = Phone(dto.client_phone)
            booking = BookingRequest(
                id=uuid.uuid4(),
                company_id=dto.company_id,
                client_name=dto.client_name,
                client_phone=phone_vo,
                services=dto.services,
                master_id=dto.master_id,
                date=dto.date,
                time_start=dto.time_start,
                time_end=dto.time_end,
                total_price=Money(dto.total_price),
                total_duration_min=dto.total_duration_min,
                payment_method=dto.payment_method,
                client_comment=dto.client_comment,
                status=BookingStatus.NEW,
            )
            self.uow.bookings.save(booking)

            event = EventEnvelope(
                type=EventTypes.BOOKING_REQUEST_CREATED,
                company_id=str(dto.company_id),
                data={
                    "booking_id": str(booking.id),
                    "client_name": booking.client_name,
                    "client_phone": str(booking.client_phone),
                    "master_id": str(booking.master_id) if booking.master_id else None,
                    "date": booking.date.isoformat(),
                    "time_start": booking.time_start.isoformat(),
                    "total_price": str(booking.total_price.amount),
                },
            )
            self.uow.record_outbox(event)
            self.uow.commit()

            return BookingRequestDTO(
                id=str(booking.id),
                company_id=str(booking.company_id),
                client_name=booking.client_name,
                client_phone=str(booking.client_phone),
                services=booking.services,
                master_id=str(booking.master_id) if booking.master_id else None,
                date=booking.date.isoformat(),
                time_start=booking.time_start.isoformat(),
                time_end=booking.time_end.isoformat(),
                total_price=booking.total_price.amount,
                total_duration_min=booking.total_duration_min,
                payment_method=booking.payment_method,
                client_comment=booking.client_comment,
                status=booking.status,
                appointment_id=None,
                version=booking.version,
                created_at=booking.created_at.isoformat(),
            )


class ConfirmBookingSagaUseCase:
    """
    Saga orchestrator for confirming online booking requests:
    1. Lock & check booking status is 'new'
    2. Call client-service: find_or_create_client
    3. Call schedule-service: create_appointment with Idempotency-Key
    4. On success: set status='confirmed', appointment_id, emit booking.request.confirmed
    5. On 409 conflict: keep status='new', raise SlotBusyError
    """

    def __init__(
        self,
        uow: BookingUnitOfWork,
        client_service: ClientServiceClientPort,
        schedule_service: ScheduleServiceClientPort,
    ):
        self.uow = uow
        self.client_service = client_service
        self.schedule_service = schedule_service

    def execute(self, company_id: uuid.UUID, booking_id: uuid.UUID, actor_name: Optional[str] = None) -> BookingRequestDTO:
        with self.uow:
            booking = self.uow.bookings.get_by_id(company_id, booking_id)
            if not booking:
                raise NotFoundError(f"Booking request {booking_id} not found")

            if booking.status != BookingStatus.NEW:
                raise AlreadyProcessedError(
                    f"Booking already processed with status: {booking.status}"
                )

            # Step 1: Find or create client
            client_data = self.client_service.find_or_create_client(
                company_id=company_id,
                full_name=booking.client_name,
                phone=str(booking.client_phone),
            )
            client_id = uuid.UUID(client_data["id"])

            # Step 2: Determine start datetime
            start_dt = datetime.combine(booking.date, booking.time_start).replace(tzinfo=timezone.utc)

            # Extract service IDs
            service_ids = []
            for s in booking.services:
                sid = s.get("service_id") or s.get("id")
                if sid:
                    service_ids.append(uuid.UUID(str(sid)))

            if not booking.master_id:
                raise ConflictError("Cannot confirm booking without assigned master_id")

            # Step 3: Create appointment in schedule service
            try:
                appt_data = self.schedule_service.create_appointment(
                    company_id=company_id,
                    client_id=client_id,
                    client_name=booking.client_name,
                    barber_id=booking.master_id,
                    service_ids=service_ids,
                    start_at=start_dt.isoformat(),
                    idempotency_key=str(booking.id),
                    comment=f"Из онлайн-заявки #{str(booking.id)[:8]}. {booking.client_comment}".strip(),
                )
            except SlotBusyError as e:
                # Slot is occupied, keep status 'new' and rethrow
                raise e

            # Step 4: Success, confirm booking
            appointment_id = uuid.UUID(appt_data["id"])
            booking.confirm(appointment_id=appointment_id, actor_name=actor_name)
            self.uow.bookings.save(booking)

            # Record event
            event = EventEnvelope(
                type=EventTypes.BOOKING_REQUEST_CONFIRMED,
                company_id=str(company_id),
                data={
                    "booking_id": str(booking.id),
                    "appointment_id": str(appointment_id),
                    "client_id": str(client_id),
                    "client_name": booking.client_name,
                    "barber_id": str(booking.master_id),
                    "start_at": start_dt.isoformat(),
                },
            )
            self.uow.record_outbox(event)
            self.uow.commit()

            return BookingRequestDTO(
                id=str(booking.id),
                company_id=str(booking.company_id),
                client_name=booking.client_name,
                client_phone=str(booking.client_phone),
                services=booking.services,
                master_id=str(booking.master_id) if booking.master_id else None,
                date=booking.date.isoformat(),
                time_start=booking.time_start.isoformat(),
                time_end=booking.time_end.isoformat(),
                total_price=booking.total_price.amount,
                total_duration_min=booking.total_duration_min,
                payment_method=booking.payment_method,
                client_comment=booking.client_comment,
                status=booking.status,
                appointment_id=str(booking.appointment_id) if booking.appointment_id else None,
                version=booking.version,
                created_at=booking.created_at.isoformat(),
            )
