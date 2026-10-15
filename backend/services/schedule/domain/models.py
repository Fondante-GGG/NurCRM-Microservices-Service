from __future__ import annotations
from dataclasses import dataclass, field
import uuid
from decimal import Decimal
from datetime import datetime, timedelta, timezone, time
from typing import List, Optional, Dict, Any

from libs.common.domain import AggregateRoot, Entity, Money, TimeSlot
from libs.common.exceptions import ValidationError, ConflictError


class AppointmentStatus:
    BOOKED = "booked"
    CONFIRMED = "confirmed"
    COMPLETED = "completed"
    CANCELED = "canceled"
    NO_SHOW = "no_show"

    ACTIVE_STATUSES = [BOOKED, CONFIRMED, COMPLETED]
    ALL = [BOOKED, CONFIRMED, COMPLETED, CANCELED, NO_SHOW]


@dataclass
class ServiceSnapshot:
    service_id: uuid.UUID
    name: str
    price: Money
    time_minutes: int

    def to_dict(self) -> Dict[str, Any]:
        return {
            "service_id": str(self.service_id),
            "name": self.name,
            "price": str(self.price.amount),
            "time_minutes": self.time_minutes,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> ServiceSnapshot:
        return cls(
            service_id=uuid.UUID(str(data["service_id"])),
            name=data["name"],
            price=Money(Decimal(str(data["price"]))),
            time_minutes=int(data["time_minutes"]),
        )


@dataclass
class Appointment(AggregateRoot):
    client_id: Optional[uuid.UUID] = None
    client_name: str = ""
    barber_id: uuid.UUID = field(default_factory=uuid.uuid4)
    services: List[ServiceSnapshot] = field(default_factory=list)
    start_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    end_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    price: Money = field(default_factory=lambda: Money(Decimal("0.00")))
    discount: Money = field(default_factory=lambda: Money(Decimal("0.00")))
    status: str = AppointmentStatus.BOOKED
    comment: str = ""
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def slot(self) -> TimeSlot:
        return TimeSlot(start_at=self.start_at, end_at=self.end_at)

    @classmethod
    def create(
        cls,
        company_id: uuid.UUID,
        client_name: str,
        barber_id: uuid.UUID,
        services: List[ServiceSnapshot],
        start_at: datetime,
        client_id: Optional[uuid.UUID] = None,
        discount: Optional[Money] = None,
        comment: str = "",
        status: str = AppointmentStatus.BOOKED,
    ) -> Appointment:
        if not services:
            raise ValidationError("Appointment must have at least one service")

        total_duration = sum(s.time_minutes for s in services)
        end_at = start_at + timedelta(minutes=total_duration)
        total_price = sum((s.price for s in services), Money(Decimal("0.00")))

        disc = discount or Money(Decimal("0.00"))
        final_price = max(Money(Decimal("0.00")), total_price - disc)

        return cls(
            id=uuid.uuid4(),
            company_id=company_id,
            client_id=client_id,
            client_name=client_name,
            barber_id=barber_id,
            services=services,
            start_at=start_at,
            end_at=end_at,
            price=final_price,
            discount=disc,
            status=status,
            comment=comment,
        )

    def transition_status(self, new_status: str) -> None:
        if self.status == new_status:
            return

        if self.status in [AppointmentStatus.COMPLETED, AppointmentStatus.CANCELED, AppointmentStatus.NO_SHOW]:
            raise ConflictError(f"Cannot change status from terminal status {self.status} to {new_status}")

        if new_status not in AppointmentStatus.ALL:
            raise ValidationError(f"Invalid status: {new_status}")

        self.status = new_status
        self.increment_version()
        self.updated_at = datetime.now(timezone.utc)


@dataclass
class MasterSchedule(Entity):
    company_id: uuid.UUID
    master_id: uuid.UUID
    day_of_week: int  # 0 to 6
    start_time: time = field(default_factory=lambda: time(9, 0))
    end_time: time = field(default_factory=lambda: time(21, 0))
    is_working: bool = True
