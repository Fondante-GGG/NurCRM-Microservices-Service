from typing import Optional, List
import uuid
from datetime import datetime, timezone
from decimal import Decimal

from libs.common.domain import Money
from backend.services.schedule.domain.models import Appointment, MasterSchedule, ServiceSnapshot, AppointmentStatus
from backend.services.schedule.domain.repositories import AppointmentRepository, MasterScheduleRepository
from backend.services.schedule.infrastructure.models import AppointmentModel, MasterScheduleModel


class DjangoAppointmentRepository(AppointmentRepository):
    def _to_domain(self, m: AppointmentModel) -> Appointment:
        services = [ServiceSnapshot.from_dict(s) for s in m.services_snapshot] if m.services_snapshot else []
        return Appointment(
            id=m.id,
            company_id=m.company_id,
            client_id=m.client_id,
            client_name=m.client_name,
            barber_id=m.barber_id,
            services=services,
            start_at=m.start_at,
            end_at=m.end_at,
            price=Money(m.price),
            discount=Money(m.discount),
            status=m.status,
            comment=m.comment or "",
            version=m.version,
            created_at=m.created_at,
            updated_at=m.updated_at,
        )

    def get_by_id(self, company_id: uuid.UUID, appt_id: uuid.UUID) -> Optional[Appointment]:
        try:
            m = AppointmentModel.objects.get(company_id=company_id, id=appt_id)
            return self._to_domain(m)
        except AppointmentModel.DoesNotExist:
            return None

    def get_by_idempotency_key(self, company_id: uuid.UUID, idempotency_key: str) -> Optional[Appointment]:
        try:
            m = AppointmentModel.objects.get(company_id=company_id, idempotency_key=idempotency_key)
            return self._to_domain(m)
        except AppointmentModel.DoesNotExist:
            return None

    def list_by_company(
        self,
        company_id: uuid.UUID,
        barber_id: Optional[uuid.UUID] = None,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
        status: Optional[str] = None,
    ) -> List[Appointment]:
        qs = AppointmentModel.objects.filter(company_id=company_id)
        if barber_id:
            qs = qs.filter(barber_id=barber_id)
        if date_from:
            qs = qs.filter(start_at__gte=date_from)
        if date_to:
            qs = qs.filter(start_at__lte=date_to)
        if status:
            qs = qs.filter(status=status)
        return [self._to_domain(m) for m in qs.order_by("start_at")]

    def get_overlapping(
        self,
        company_id: uuid.UUID,
        barber_id: Optional[uuid.UUID],
        start_at: datetime,
        end_at: datetime,
        exclude_id: Optional[uuid.UUID] = None,
    ) -> List[Appointment]:
        if not barber_id:
            return []
        qs = AppointmentModel.objects.filter(
            company_id=company_id,
            barber_id=barber_id,
            status__in=AppointmentStatus.ACTIVE_STATUSES,
            start_at__lt=end_at,
            end_at__gt=start_at,
        )
        if exclude_id:
            qs = qs.exclude(id=exclude_id)
        return [self._to_domain(m) for m in qs]

    def save(self, appt: Appointment) -> None:
        from django.db import IntegrityError
        try:
            AppointmentModel.objects.update_or_create(
                id=appt.id,
                company_id=appt.company_id,
                defaults={
                    "client_id": appt.client_id,
                    "client_name": appt.client_name,
                    "barber_id": appt.barber_id,
                    "services_snapshot": [s.to_dict() for s in appt.services],
                    "start_at": appt.start_at,
                    "end_at": appt.end_at,
                    "price": appt.price.amount,
                    "discount": appt.discount.amount,
                    "status": appt.status,
                    "comment": appt.comment,
                    "idempotency_key": appt.idempotency_key,
                    "version": appt.version,
                    "updated_at": appt.updated_at,
                },
            )
        except IntegrityError as e:
            err_str = str(e).lower()
            if "no_overlap" in err_str or "exclusion" in err_str:
                raise SlotBusyError("Master slot is already booked for this interval")
            if "idempotency_key" in err_str:
                # Concurrent duplicate idempotency key
                pass
            else:
                raise

    def delete(self, company_id: uuid.UUID, appt_id: uuid.UUID) -> None:
        AppointmentModel.objects.filter(company_id=company_id, id=appt_id).delete()

    def auto_complete_expired(self, now_time: datetime) -> List[Appointment]:
        expired = list(AppointmentModel.objects.filter(
            status__in=[AppointmentStatus.BOOKED, AppointmentStatus.CONFIRMED],
            end_at__lte=now_time,
        ).select_for_update())

        result = []
        for m in expired:
            m.status = AppointmentStatus.COMPLETED
            m.version += 1
            m.updated_at = datetime.now(timezone.utc)
            m.save()
            result.append(self._to_domain(m))
        return result


class DjangoMasterScheduleRepository(MasterScheduleRepository):
    def _to_domain(self, m: MasterScheduleModel) -> MasterSchedule:
        return MasterSchedule(
            id=m.id,
            company_id=m.company_id,
            master_id=m.master_id,
            day_of_week=m.day_of_week,
            start_time=m.start_time,
            end_time=m.end_time,
            is_working=m.is_working,
        )

    def get_by_master_and_day(self, company_id: uuid.UUID, master_id: uuid.UUID, day_of_week: int) -> Optional[MasterSchedule]:
        try:
            m = MasterScheduleModel.objects.get(company_id=company_id, master_id=master_id, day_of_week=day_of_week)
            return self._to_domain(m)
        except MasterScheduleModel.DoesNotExist:
            return None

    def list_by_master(self, company_id: uuid.UUID, master_id: uuid.UUID) -> List[MasterSchedule]:
        qs = MasterScheduleModel.objects.filter(company_id=company_id, master_id=master_id)
        return [self._to_domain(m) for m in qs]

    def save(self, schedule: MasterSchedule) -> None:
        MasterScheduleModel.objects.update_or_create(
            company_id=schedule.company_id,
            master_id=schedule.master_id,
            day_of_week=schedule.day_of_week,
            defaults={
                "start_time": schedule.start_time,
                "end_time": schedule.end_time,
                "is_working": schedule.is_working,
            },
        )
