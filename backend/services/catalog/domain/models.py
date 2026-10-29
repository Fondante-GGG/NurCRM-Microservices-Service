from __future__ import annotations
from dataclasses import dataclass, field
import uuid
from decimal import Decimal
from datetime import datetime, timezone
from typing import List, Optional

from libs.common.domain import AggregateRoot, Money
from libs.common.exceptions import ValidationError


@dataclass
class ServiceCategory(AggregateRoot):
    name: str = ""
    is_active: bool = True
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class Service(AggregateRoot):
    category_id: uuid.UUID = field(default_factory=uuid.uuid4)
    name: str = ""
    price: Money = field(default_factory=lambda: Money(Decimal("0.00")))
    time_minutes: int = 30
    barbers: List[uuid.UUID] = field(default_factory=list)
    is_active: bool = True
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self):
        if self.time_minutes <= 0:
            raise ValidationError("Service duration (time_minutes) must be greater than 0")
        if self.price.amount < 0:
            raise ValidationError("Service price cannot be negative")

    def is_master_allowed(self, master_id: uuid.UUID) -> bool:
        if not self.barbers:
            return True  # If empty, all masters are allowed
        return master_id in self.barbers


@dataclass
class SalaryRate(AggregateRoot):
    service_id: uuid.UUID = field(default_factory=uuid.uuid4)
    master_id: Optional[uuid.UUID] = None  # None means default rate for all masters
    percent: Decimal = field(default_factory=lambda: Decimal("0.00"))
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self):
        if self.percent < Decimal("0.00") or self.percent > Decimal("100.00"):
            raise ValidationError("Salary rate percent must be between 0 and 100")


@dataclass
class Product(AggregateRoot):
    name: str = ""
    sku: str = ""
    category: str = ""
    price: Money = field(default_factory=lambda: Money(Decimal("0.00")))
    cost_price: Money = field(default_factory=lambda: Money(Decimal("0.00")))
    wholesale_price: Optional[Money] = None
    unit_code: str = "pcs"
    minimum_quantity: Decimal = field(default_factory=lambda: Decimal("1.000"))
    quantity_step: Decimal = field(default_factory=lambda: Decimal("1.000"))
    attributes: dict = field(default_factory=dict)
    is_active: bool = True

    def __post_init__(self):
        self.name = self.name.strip()
        self.sku = self.sku.strip()
        self.unit_code = self.unit_code.strip()
        if not self.name:
            raise ValidationError("Product name is required")
        if not self.unit_code:
            raise ValidationError("Product unit_code is required")
        if self.price.amount < 0 or self.cost_price.amount < 0:
            raise ValidationError("Product prices cannot be negative")
        if self.wholesale_price and self.wholesale_price.amount < 0:
            raise ValidationError("Product wholesale price cannot be negative")
        if self.minimum_quantity < 0 or self.quantity_step <= 0:
            raise ValidationError("Product quantity limits are invalid")

    def validate_quantity(self, quantity: Decimal) -> None:
        if quantity < self.minimum_quantity or quantity % self.quantity_step != 0:
            raise ValidationError(
                "Quantity must satisfy the product minimum and step",
                details={
                    "minimum_quantity": str(self.minimum_quantity),
                    "quantity_step": str(self.quantity_step),
                },
            )
