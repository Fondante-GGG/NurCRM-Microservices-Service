from __future__ import annotations
from dataclasses import dataclass, field
import uuid
from decimal import Decimal
from datetime import datetime, date, time, timezone
from typing import List, Optional, Dict, Any

from libs.common.domain import AggregateRoot, Money, Phone
from libs.common.exceptions import ValidationError, AlreadyProcessedError


class BookingStatus:
    NEW = "new"
    CONFIRMED = "confirmed"
    NO_SHOW = "no_show"
    SPAM = "spam"

    CHOICES = [NEW, CONFIRMED, NO_SHOW, SPAM]


@dataclass
class BookingRequest(AggregateRoot):
    client_name: str = ""
    client_phone: Phone = field(default_factory=lambda: Phone("+996555000000"))
    services: List[Dict[str, Any]] = field(default_factory=list)
    master_id: Optional[uuid.UUID] = None
    date: date = field(default_factory=date.today)
    time_start: time = field(default_factory=lambda: time(9, 0))
    time_end: time = field(default_factory=lambda: time(9, 30))
    total_price: Money = field(default_factory=lambda: Money(Decimal("0.00")))
    total_duration_min: int = 30
    payment_method: str = "cash"
    client_comment: str = ""
    status: str = BookingStatus.NEW
    appointment_id: Optional[uuid.UUID] = None
    confirmed_by: Optional[str] = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def confirm(self, appointment_id: uuid.UUID, actor_name: Optional[str] = None) -> None:
        if self.status != BookingStatus.NEW:
            raise AlreadyProcessedError(
                message=f"Booking request already processed with status: {self.status}",
                details={"status": self.status, "confirmed_by": self.confirmed_by},
            )
        self.status = BookingStatus.CONFIRMED
        self.appointment_id = appointment_id
        self.confirmed_by = actor_name
        self.increment_version()
        self.updated_at = datetime.now(timezone.utc)
