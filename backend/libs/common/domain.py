from __future__ import annotations
from dataclasses import dataclass, field
from decimal import Decimal
from datetime import datetime, timezone
import uuid
import re
from typing import List, Protocol, TypeVar, Optional, Any


@dataclass(frozen=True)
class Money:
    amount: Decimal
    currency: str = "KGS"

    def __post_init__(self):
        if object.__getattribute__(self, "amount") is None:
            raise ValueError("Amount cannot be None")
        object.__setattr__(
            self,
            "amount",
            Decimal(str(self.amount)).quantize(Decimal("0.01")),
        )

    def __add__(self, other: Money) -> Money:
        if self.currency != other.currency:
            raise ValueError(f"Cannot add money with different currencies: {self.currency} and {other.currency}")
        return Money(self.amount + other.amount, self.currency)

    def __sub__(self, other: Money) -> Money:
        if self.currency != other.currency:
            raise ValueError(f"Cannot subtract money with different currencies: {self.currency} and {other.currency}")
        return Money(self.amount - other.amount, self.currency)

    def __mul__(self, factor: Decimal | float | int) -> Money:
        return Money(self.amount * Decimal(str(factor)), self.currency)

    def __lt__(self, other: Money) -> bool:
        if self.currency != other.currency:
            raise ValueError(f"Cannot compare money with different currencies: {self.currency} and {other.currency}")
        return self.amount < other.amount

    def __le__(self, other: Money) -> bool:
        if self.currency != other.currency:
            raise ValueError(f"Cannot compare money with different currencies: {self.currency} and {other.currency}")
        return self.amount <= other.amount

    def __gt__(self, other: Money) -> bool:
        if self.currency != other.currency:
            raise ValueError(f"Cannot compare money with different currencies: {self.currency} and {other.currency}")
        return self.amount > other.amount

    def __ge__(self, other: Money) -> bool:
        if self.currency != other.currency:
            raise ValueError(f"Cannot compare money with different currencies: {self.currency} and {other.currency}")
        return self.amount >= other.amount


@dataclass(frozen=True)
class Phone:
    value: str

    def __post_init__(self):
        cleaned = re.sub(r"[^\d+]", "", self.value)
        if not cleaned:
            raise ValueError("Phone number cannot be empty")
        if not cleaned.startswith("+"):
            # Normalize CIS/KG numbers: e.g. 996... or 0...
            if cleaned.startswith("0") and len(cleaned) == 10:
                cleaned = "+996" + cleaned[1:]
            elif not cleaned.startswith("+"):
                cleaned = "+" + cleaned
        if len(cleaned) < 10 or len(cleaned) > 16:
            raise ValueError(f"Invalid international phone number format: {self.value}")
        object.__setattr__(self, "value", cleaned)

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True)
class TimeSlot:
    start_at: datetime
    end_at: datetime

    def __post_init__(self):
        if self.start_at >= self.end_at:
            raise ValueError(f"start_at ({self.start_at}) must be before end_at ({self.end_at})")

    @property
    def duration_minutes(self) -> int:
        return int((self.end_at - self.start_at).total_seconds() / 60)

    def overlaps_with(self, other: TimeSlot) -> bool:
        return self.start_at < other.end_at and other.start_at < self.end_at


@dataclass
class DomainEvent:
    event_id: uuid.UUID = field(default_factory=uuid.uuid4)
    occurred_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    company_id: Optional[uuid.UUID] = None
    event_type: str = "domain.event"
    version: int = 1
    data: dict[str, Any] = field(default_factory=dict)


@dataclass
class Entity:
    id: uuid.UUID

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Entity):
            return False
        return self.id == other.id

    def __hash__(self) -> int:
        return hash(self.id)


@dataclass
class AggregateRoot(Entity):
    company_id: uuid.UUID
    version: int = 1
    _domain_events: List[DomainEvent] = field(default_factory=list, init=False, repr=False)

    def record_event(self, event: DomainEvent) -> None:
        if not event.company_id:
            event.company_id = self.company_id
        self._domain_events.append(event)

    def collect_events(self) -> List[DomainEvent]:
        events = list(self._domain_events)
        self._domain_events.clear()
        return events

    def increment_version(self) -> None:
        self.version += 1


T = TypeVar("T", bound=AggregateRoot)


class Repository(Protocol[T]):
    def get_by_id(self, company_id: uuid.UUID, entity_id: uuid.UUID) -> Optional[T]:
        ...

    def add(self, entity: T) -> None:
        ...

    def update(self, entity: T) -> None:
        ...


class UnitOfWork(Protocol):
    def __enter__(self) -> "UnitOfWork":
        ...

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        ...

    def commit(self) -> None:
        ...

    def rollback(self) -> None:
        ...
