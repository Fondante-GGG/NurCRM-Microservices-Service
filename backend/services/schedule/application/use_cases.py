from __future__ import annotations
import uuid
from decimal import Decimal
from datetime import datetime, timezone, timedelta
from typing import Protocol, List, Optional, Dict, Any

from libs.common.domain import Money
from libs.common.events import EventEnvelope, EventTypes
from libs.common.exceptions import NotFoundError, SlotBusyError, VersionConflictError, ValidationError
from backend.services.schedule.domain.models import Appointment, AppointmentStatus, ServiceSnapshot
from backend.services.schedule.domain.repositories import AppointmentRepository, MasterScheduleRepository
from backend.services.schedule.application.dto import (
    CreateAppointmentDTO,
    UpdateAppointmentDTO,
    AppointmentDTO,
    BusySlotDTO,
)


class ScheduleUnitOfWork(Protocol):
    appointments: AppointmentRepository
    master_schedules: MasterScheduleRepository

    def __enter__(self) -> "ScheduleUnitOfWork":
        ...

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        ...

    def commit(self) -> None:
        ...

    def record_outbox(self, event: EventEnvelope) -> None:
        ...


class CatalogClientPort(Protocol):
    def get_services(self, company_id: uuid.UUID, service_ids: List[uuid.UUID]) -> List[ServiceSnapshot]:
        ...


class CreateAppointmentUseCase:
    def __init__(self, uow: ScheduleUnitOfWork, catalog_client: CatalogClientPort):
        self.uow = uow
        self.catalog = catalog_client

    def execute(self, dto: CreateAppointmentDTO) -> AppointmentDTO:
        with self.uow:
            # 1. Fetch service snapshots from catalog
            services = self.catalog.get_services(dto.company_id, dto.service_ids)
            if not services:
                raise ValidationError("No valid services found for appointment")

            # 2. Build appointment aggregate to compute duration & end_at
            discount_money = Money(dto.discount) if dto.discount is not None else None
            appt = Appointment.create(
                company_id=dto.company_id,
                client_id=dto.client_id,
                client_name=dto.client_name,
                barber_id=dto.barber_id,
                services=services,
                start_at=dto.start_at,
                discount=discount_money,
                comment=dto.comment,
                status=dto.status,
            )

            # 3. Conflict resolution / Overlap check
            overlapping = self.uow.appointments.get_overlapping(
                company_id=dto.company_id,
                barber_id=dto.barber_id,
                start_at=appt.start_at,
                end_at=appt.end_at,
            )
            if overlapping:
                raise SlotBusyError(
                    f"Master is already booked between {overlapping[0].start_at.isoformat()} and {overlapping[0].end_at.isoformat()}"
                )

            # 4. Save
            self.uow.appointments.save(appt)

            # 5. Record outbox event
            event = EventEnvelope(
                type=EventTypes.SCHEDULE_APPOINTMENT_CREATED,
                company_id=str(dto.company_id),
                data={
                    "appointment_id": str(appt.id),
                    "client_id": str(appt.client_id) if appt.client_id else None,
                    "client_name": appt.client_name,
                    "barber_id": str(appt.barber_id),
                    "start_at": appt.start_at.isoformat(),
                    "end_at": appt.end_at.isoformat(),
                    "price": str(appt.price.amount),
                    "services": [s.to_dict() for s in appt.services],
                    "status": appt.status,
                },
            )
            self.uow.record_outbox(event)
            self.uow.commit()

            return AppointmentDTO(
                id=str(appt.id),
                company_id=str(appt.company_id),
                client_id=str(appt.client_id) if appt.client_id else None,
                client_name=appt.client_name,
                barber_id=str(appt.barber_id),
                services=[s.to_dict() for s in appt.services],
                start_at=appt.start_at.isoformat(),
                end_at=appt.end_at.isoformat(),
                price=appt.price.amount,
                discount=appt.discount.amount,
                status=appt.status,
                comment=appt.comment,
                version=appt.version,
            )


class UpdateAppointmentUseCase:
    def __init__(self, uow: ScheduleUnitOfWork, catalog_client: Optional[CatalogClientPort] = None):
        self.uow = uow
        self.catalog = catalog_client

    def execute(self, company_id: uuid.UUID, appt_id: uuid.UUID, dto: UpdateAppointmentDTO) -> AppointmentDTO:
        with self.uow:
            appt = self.uow.appointments.get_by_id(company_id, appt_id)
            if not appt:
                raise NotFoundError(f"Appointment {appt_id} not found")

            # Check optimistic lock
            if dto.expected_version is not None and dto.expected_version != appt.version:
                raise VersionConflictError(current_version=appt.version)

            if dto.client_name is not None:
                appt.client_name = dto.client_name
            if dto.comment is not None:
                appt.comment = dto.comment
            if dto.discount is not None:
                appt.discount = Money(dto.discount)

            # Check if timing or barber changed
            services_changed = dto.service_ids is not None and self.catalog is not None
            if services_changed:
                appt.services = self.catalog.get_services(company_id, dto.service_ids)  # type: ignore

            start_at_changed = dto.start_at is not None and dto.start_at != appt.start_at
            if start_at_changed:
                appt.start_at = dto.start_at  # type: ignore

            if services_changed or start_at_changed:
                total_duration = sum(s.time_minutes for s in appt.services)
                appt.end_at = appt.start_at + timedelta(minutes=total_duration)
                total_price = sum((s.price for s in appt.services), Money(Decimal("0.00")))
                appt.price = max(Money(Decimal("0.00")), total_price - appt.discount)

            barber_changed = dto.barber_id is not None and dto.barber_id != appt.barber_id
            if barber_changed:
                appt.barber_id = dto.barber_id  # type: ignore

            if start_at_changed or services_changed or barber_changed:
                overlapping = self.uow.appointments.get_overlapping(
                    company_id=company_id,
                    barber_id=appt.barber_id,
                    start_at=appt.start_at,
                    end_at=appt.end_at,
                    exclude_id=appt.id,
                )
                if overlapping:
                    raise SlotBusyError("Slot is already booked for this master")

            appt.increment_version()
            appt.updated_at = datetime.now(timezone.utc)
            self.uow.appointments.save(appt)

            event = EventEnvelope(
                type=EventTypes.SCHEDULE_APPOINTMENT_UPDATED,
                company_id=str(company_id),
                data={
                    "appointment_id": str(appt.id),
                    "barber_id": str(appt.barber_id),
                    "start_at": appt.start_at.isoformat(),
                    "end_at": appt.end_at.isoformat(),
                    "status": appt.status,
                    "version": appt.version,
                },
            )
            self.uow.record_outbox(event)
            self.uow.commit()

            return AppointmentDTO(
                id=str(appt.id),
                company_id=str(appt.company_id),
                client_id=str(appt.client_id) if appt.client_id else None,
                client_name=appt.client_name,
                barber_id=str(appt.barber_id),
                services=[s.to_dict() for s in appt.services],
                start_at=appt.start_at.isoformat(),
                end_at=appt.end_at.isoformat(),
                price=appt.price.amount,
                discount=appt.discount.amount,
                status=appt.status,
                comment=appt.comment,
                version=appt.version,
            )


class ChangeAppointmentStatusUseCase:
    def __init__(self, uow: ScheduleUnitOfWork):
        self.uow = uow

    def execute(self, company_id: uuid.UUID, appt_id: uuid.UUID, new_status: str, expected_version: Optional[int] = None) -> AppointmentDTO:
        with self.uow:
            appt = self.uow.appointments.get_by_id(company_id, appt_id)
            if not appt:
                raise NotFoundError(f"Appointment {appt_id} not found")

            if expected_version is not None and expected_version != appt.version:
                raise VersionConflictError(current_version=appt.version)

            appt.transition_status(new_status)
            self.uow.appointments.save(appt)

            event_type = EventTypes.SCHEDULE_APPOINTMENT_UPDATED
            if new_status == AppointmentStatus.CANCELED:
                event_type = EventTypes.SCHEDULE_APPOINTMENT_CANCELED
            elif new_status == AppointmentStatus.COMPLETED:
                event_type = EventTypes.SCHEDULE_APPOINTMENT_COMPLETED

            event = EventEnvelope(
                type=event_type,
                company_id=str(company_id),
                data={
                    "appointment_id": str(appt.id),
                    "company_id": str(appt.company_id),
                    "barber_id": str(appt.barber_id),
                    "price": str(appt.price.amount),
                    "services": [s.to_dict() for s in appt.services],
                    "status": appt.status,
                    "version": appt.version,
                },
            )
            self.uow.record_outbox(event)
            self.uow.commit()

            return AppointmentDTO(
                id=str(appt.id),
                company_id=str(appt.company_id),
                client_id=str(appt.client_id) if appt.client_id else None,
                client_name=appt.client_name,
                barber_id=str(appt.barber_id),
                services=[s.to_dict() for s in appt.services],
                start_at=appt.start_at.isoformat(),
                end_at=appt.end_at.isoformat(),
                price=appt.price.amount,
                discount=appt.discount.amount,
                status=appt.status,
                comment=appt.comment,
                version=appt.version,
            )


class AutoCompleteAppointmentsUseCase:
    def __init__(self, uow: ScheduleUnitOfWork):
        self.uow = uow

    def execute(self, now_time: Optional[datetime] = None) -> int:
        now_dt = now_time or datetime.now(timezone.utc)
        with self.uow:
            completed_appts = self.uow.appointments.auto_complete_expired(now_dt)
            for appt in completed_appts:
                event = EventEnvelope(
                    type=EventTypes.SCHEDULE_APPOINTMENT_COMPLETED,
                    company_id=str(appt.company_id),
                    data={
                        "appointment_id": str(appt.id),
                        "company_id": str(appt.company_id),
                        "barber_id": str(appt.barber_id),
                        "price": str(appt.price.amount),
                        "services": [s.to_dict() for s in appt.services],
                        "status": appt.status,
                        "version": appt.version,
                    },
                )
                self.uow.record_outbox(event)
            self.uow.commit()
            return len(completed_appts)


class GetBusyIntervalsUseCase:
    def __init__(self, uow: ScheduleUnitOfWork):
        self.uow = uow

    def execute(self, company_id: uuid.UUID, barber_id: uuid.UUID, target_date: datetime.date) -> List[BusySlotDTO]:
        with self.uow:
            start_of_day = datetime(target_date.year, target_date.month, target_date.day, 0, 0, 0, tzinfo=timezone.utc)
            end_of_day = start_of_day + timedelta(days=1)
            appts = self.uow.appointments.list_by_company(
                company_id=company_id,
                barber_id=barber_id,
                date_from=start_of_day,
                date_to=end_of_day,
            )
            active = [a for a in appts if a.status in AppointmentStatus.ACTIVE_STATUSES]
            return [BusySlotDTO(start_at=a.start_at.isoformat(), end_at=a.end_at.isoformat()) for a in active]
