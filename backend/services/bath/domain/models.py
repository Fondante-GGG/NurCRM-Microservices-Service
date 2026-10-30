import math
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from typing import List, Optional

from libs.common.domain import AggregateRoot, Entity, Money


class InsufficientStockError(Exception):
    """Raised when stock deduction exceeds available quantity."""
    pass


class DebtOutstandingError(Exception):
    """Raised when guest tries to exit with unpaid balance without debt override."""
    pass


class DebtLimitExceededError(Exception):
    """Raised when in-house order exceeds client's allowed debt limit."""
    pass


@dataclass
class LockerCategory(Entity):
    company_id: uuid.UUID
    branch_id: uuid.UUID
    name: str
    code: str
    count: int = 20
    sort: int = 0


@dataclass
class Locker(Entity):
    company_id: uuid.UUID
    branch_id: uuid.UUID
    category_id: uuid.UUID
    number: int
    code: str  # e.g. "M12"
    is_broken: bool = False
    bracelet_tag: Optional[str] = None


@dataclass
class EntryTariff(Entity):
    company_id: uuid.UUID
    branch_id: uuid.UUID
    name: str
    price: Money
    included_hours: int = 0  # 0 = unmetered / unlimited
    extra_per_hour: Money = field(default_factory=lambda: Money(Decimal("0.00")))
    is_subscription: bool = False


@dataclass
class VisitItem:
    id: uuid.UUID
    source: str  # 'entry', 'bar', 'extra', 'service', 'rent', 'time'
    name: str
    price: Money
    qty: int = 1
    cost: Money = field(default_factory=lambda: Money(Decimal("0.00")))
    employee_id: Optional[uuid.UUID] = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    deleted_at: Optional[datetime] = None
    deleted_by: Optional[uuid.UUID] = None
    delete_reason: Optional[str] = None

    @property
    def total(self) -> Money:
        return Money(self.price.amount * Decimal(self.qty))

    @property
    def is_active(self) -> bool:
        return self.deleted_at is None


@dataclass
class Visit(AggregateRoot):
    branch_id: uuid.UUID = field(default_factory=uuid.uuid4)
    locker_id: uuid.UUID = field(default_factory=uuid.uuid4)
    tariff_id: uuid.UUID = field(default_factory=uuid.uuid4)
    client_id: Optional[uuid.UUID] = None
    group_id: Optional[uuid.UUID] = None
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    closed_at: Optional[datetime] = None
    status: str = "open"  # 'open', 'paid', 'debt'
    closed_by: Optional[uuid.UUID] = None
    items: List[VisitItem] = field(default_factory=list)

    def add_item(
        self,
        source: str,
        name: str,
        price: Money,
        qty: int = 1,
        cost: Optional[Money] = None,
        employee_id: Optional[uuid.UUID] = None,
    ) -> VisitItem:
        if self.status != "open":
            raise ValueError(f"Cannot add items to closed visit ({self.status})")
        item = VisitItem(
            id=uuid.uuid4(),
            source=source,
            name=name,
            price=price,
            qty=qty,
            cost=cost or Money(Decimal("0.00")),
            employee_id=employee_id,
        )
        self.items.append(item)
        self.increment_version()
        return item

    def remove_item(
        self,
        item_id: uuid.UUID,
        reason: str,
        employee_id: uuid.UUID,
    ) -> None:
        for item in self.items:
            if item.id == item_id and item.is_active:
                if item.source == "entry":
                    raise ValueError("Cannot delete entry position")
                item.deleted_at = datetime.now(timezone.utc)
                item.deleted_by = employee_id
                item.delete_reason = reason
                self.increment_version()
                return
        raise ValueError(f"Active item {item_id} not found in visit")

    def calculate_overage_charge(self, now: datetime, tariff: EntryTariff) -> Money:
        if tariff.included_hours <= 0 or tariff.extra_per_hour.amount <= 0:
            return Money(Decimal("0.00"))
        
        minutes_spent = int((now - self.started_at).total_seconds() / 60)
        included_minutes = tariff.included_hours * 60
        overage_minutes = minutes_spent - included_minutes
        if overage_minutes > 0:
            extra_hours = math.ceil(overage_minutes / 60)
            return Money(Decimal(extra_hours) * tariff.extra_per_hour.amount)
        return Money(Decimal("0.00"))

    def calculate_total_debt(self, now: datetime, tariff: EntryTariff) -> Money:
        total = Decimal("0.00")
        for item in self.items:
            if item.is_active:
                total += item.total.amount
        overage = self.calculate_overage_charge(now, tariff)
        return Money(total + overage.amount)

    def close_visit(
        self,
        paid_amount: Money,
        total_debt: Money,
        closed_by: uuid.UUID,
        allow_debt: bool = False,
    ) -> None:
        if paid_amount < total_debt and not allow_debt:
            diff = total_debt - paid_amount
            raise DebtOutstandingError(f"Outstanding debt of {diff.amount} KGS. Cannot release locker without payment or debt permission.")
        self.closed_at = datetime.now(timezone.utc)
        self.closed_by = closed_by
        self.status = "paid" if paid_amount >= total_debt else "debt"
        self.increment_version()


@dataclass
class BarItem(Entity):
    company_id: uuid.UUID
    branch_id: uuid.UUID
    name: str
    price: Money
    cost: Money
    stock: Optional[int] = None  # None = uncounted (tea, hookah, etc.)
    category_id: Optional[uuid.UUID] = None

    def deduct_stock(self, qty: int) -> Optional[str]:
        if self.stock is None:
            return None
        if self.stock < qty:
            raise InsufficientStockError(f"Not enough stock for {self.name}: requested {qty}, available {self.stock}")
        self.stock -= qty
        if self.stock == 0:
            return "out_of_stock"
        elif self.stock <= 5:
            return "low_stock"
        return None

    @property
    def profit_per_unit(self) -> Money:
        return Money(self.price.amount - self.cost.amount)

    @property
    def margin_pct(self) -> Decimal:
        if self.price.amount <= 0:
            return Decimal("0.00")
        return ((self.price.amount - self.cost.amount) / self.price.amount * Decimal("100.00")).quantize(Decimal("0.01"))


@dataclass
class MasterService(Entity):
    company_id: uuid.UUID
    branch_id: uuid.UUID
    name: str
    price: Money
    role: str = "Мастер"

    @staticmethod
    def calculate_commission(
        price: Money,
        pct: Decimal = Decimal("0.00"),
        fixed_per_service: Optional[Money] = None,
    ) -> Money:
        amount = price.amount * (pct / Decimal("100.00"))
        if fixed_per_service:
            amount += fixed_per_service.amount
        return Money(amount)


@dataclass
class RoomBooking(Entity):
    company_id: uuid.UUID
    branch_id: uuid.UUID
    room_id: uuid.UUID
    who: str
    from_time: datetime
    to_time: datetime
    price_per_hour: Money
    min_hours: int = 2
    prepaid: Money = field(default_factory=lambda: Money(Decimal("0.00")))
    status: str = "booked"  # 'booked', 'active', 'closed'

    def calculate_rent(self) -> Money:
        hours = max(
            int(math.ceil((self.to_time - self.from_time).total_seconds() / 3600)),
            self.min_hours,
        )
        return Money(Decimal(hours) * self.price_per_hour.amount)
