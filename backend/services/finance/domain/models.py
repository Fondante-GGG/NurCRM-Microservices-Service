from __future__ import annotations
from dataclasses import dataclass, field
import uuid
from decimal import Decimal
from datetime import datetime, date, timezone
from typing import Optional

from libs.common.domain import AggregateRoot, Entity, Money
from libs.common.exceptions import ValidationError, ShiftAlreadyOpenError, ConflictError


@dataclass
class Accrual(AggregateRoot):
    appointment_id: uuid.UUID = field(default_factory=uuid.uuid4)
    master_id: uuid.UUID = field(default_factory=uuid.uuid4)
    service_id: Optional[uuid.UUID] = None
    amount: Money = field(default_factory=lambda: Money(Decimal("0.00")))
    percent: Decimal = field(default_factory=lambda: Decimal("0.00"))
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @classmethod
    def calculate(
        cls,
        company_id: uuid.UUID,
        appointment_id: uuid.UUID,
        master_id: uuid.UUID,
        service_price: Money,
        percent: Decimal,
        service_id: Optional[uuid.UUID] = None,
    ) -> Accrual:
        rate = max(Decimal("0.00"), min(percent, Decimal("100.00")))
        accrual_amount = (service_price * (rate / Decimal("100.00")))
        return cls(
            id=uuid.uuid4(),
            company_id=company_id,
            appointment_id=appointment_id,
            master_id=master_id,
            service_id=service_id,
            amount=accrual_amount,
            percent=rate,
        )


@dataclass
class SalaryPayout(AggregateRoot):
    master_id: uuid.UUID = field(default_factory=uuid.uuid4)
    amount: Money = field(default_factory=lambda: Money(Decimal("0.00")))
    date: date = field(default_factory=date.today)
    cashbox: str = "Основная касса"
    comment: Optional[str] = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self):
        if self.amount.amount <= Decimal("0.00"):
            raise ValidationError("Payout amount must be greater than zero")


@dataclass
class CashShift(AggregateRoot):
    user_id: uuid.UUID = field(default_factory=uuid.uuid4)
    cashbox: str = "Основная касса"
    opening_cash: Money = field(default_factory=lambda: Money(Decimal("0.00")))
    closing_cash: Optional[Money] = None
    sales_total: Money = field(default_factory=lambda: Money(Decimal("0.00")))
    sales_count: int = 0
    status: str = "open"  # open, closed
    opened_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    closed_at: Optional[datetime] = None

    def close(self, closing_cash: Money, sales_total: Money, sales_count: int) -> None:
        if self.status == "closed":
            raise ConflictError("Shift is already closed")
        self.status = "closed"
        self.closing_cash = closing_cash
        self.sales_total = sales_total
        self.sales_count = sales_count
        self.closed_at = datetime.now(timezone.utc)
        self.increment_version()


@dataclass
class Material(Entity):
    company_id: uuid.UUID
    name: str
    unit: str = "шт"
    current_stock: Decimal = field(default_factory=lambda: Decimal("0.000"))
    cost_price: Money = field(default_factory=lambda: Money(Decimal("0.00")))
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class InventoryMovement(Entity):
    company_id: uuid.UUID
    material_id: uuid.UUID
    movement_type: str  # incoming, write_off, sale
    quantity: Decimal
    price: Money
    reason: Optional[str] = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
