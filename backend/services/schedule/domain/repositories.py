from typing import Optional, List, Protocol
import uuid
from datetime import datetime, date
from backend.services.schedule.domain.models import Appointment, MasterSchedule


class AppointmentRepository(Protocol):
    def get_by_id(self, company_id: uuid.UUID, appt_id: uuid.UUID) -> Optional[Appointment]:
        ...

    def list_by_company(
        self,
        company_id: uuid.UUID,
        barber_id: Optional[uuid.UUID] = None,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
        status: Optional[str] = None,
    ) -> List[Appointment]:
        ...

    def get_overlapping(
        self,
        company_id: uuid.UUID,
        barber_id: Optional[uuid.UUID],
        start_at: datetime,
        end_at: datetime,
        exclude_id: Optional[uuid.UUID] = None,
    ) -> List[Appointment]:
        ...

    def save(self, appt: Appointment) -> None:
        ...

    def delete(self, company_id: uuid.UUID, appt_id: uuid.UUID) -> None:
        ...

    def auto_complete_expired(self, now_time: datetime) -> List[Appointment]:
        ...


class MasterScheduleRepository(Protocol):
    def get_by_master_and_day(self, company_id: uuid.UUID, master_id: uuid.UUID, day_of_week: int) -> Optional[MasterSchedule]:
        ...

    def list_by_master(self, company_id: uuid.UUID, master_id: uuid.UUID) -> List[MasterSchedule]:
        ...

    def save(self, schedule: MasterSchedule) -> None:
        ...
