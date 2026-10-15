from typing import List
from django.db import transaction
import uuid

from libs.common.events import EventEnvelope
from backend.services.schedule.application.use_cases import ScheduleUnitOfWork
from backend.services.schedule.infrastructure.models import OutboxModel
from backend.services.schedule.infrastructure.repositories import (
    DjangoAppointmentRepository,
    DjangoMasterScheduleRepository,
)


class DjangoScheduleUnitOfWork(ScheduleUnitOfWork):
    def __init__(self):
        self.appointments = DjangoAppointmentRepository()
        self.master_schedules = DjangoMasterScheduleRepository()
        self._events_to_record: List[EventEnvelope] = []
        self._transaction = None

    def __enter__(self) -> "DjangoScheduleUnitOfWork":
        self._transaction = transaction.atomic()
        self._transaction.__enter__()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None:
            self.rollback()
            self._transaction.__exit__(exc_type, exc_val, exc_tb)
            return False
        return self._transaction.__exit__(exc_type, exc_val, exc_tb)

    def record_outbox(self, event: EventEnvelope) -> None:
        self._events_to_record.append(event)

    def commit(self) -> None:
        for event in self._events_to_record:
            OutboxModel.objects.create(
                event_id=uuid.UUID(event.event_id),
                event_type=event.type,
                payload=event.to_dict(),
                status="pending",
            )
        self._events_to_record.clear()

    def rollback(self) -> None:
        self._events_to_record.clear()
