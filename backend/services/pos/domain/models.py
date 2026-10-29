from dataclasses import dataclass, field
from decimal import Decimal
import uuid

from libs.common.domain import AggregateRoot, Money
from libs.common.exceptions import ValidationError


@dataclass(frozen=True)
class CatalogProduct:
    id: uuid.UUID
    name: str
    sku: str
    price: Decimal
    unit_code: str
    minimum_quantity: Decimal
    quantity_step: Decimal
    is_active: bool

    def validate_quantity(self, quantity: Decimal, unit_code: str) -> None:
        if not self.is_active:
            raise ValidationError(f"Product {self.id} is inactive")
        if unit_code != self.unit_code:
            raise ValidationError(
                f"Product {self.id} must be sold in {self.unit_code}",
                details={"expected_unit_code": self.unit_code},
            )
        if quantity <= 0 or quantity < self.minimum_quantity or quantity % self.quantity_step != 0:
            raise ValidationError(
                f"Quantity for product {self.id} does not satisfy its minimum and step",
                details={
                    "minimum_quantity": str(self.minimum_quantity),
                    "quantity_step": str(self.quantity_step),
                },
            )


@dataclass
class SaleLine:
    product_id: uuid.UUID
    name: str
    sku: str
    quantity: Decimal
    unit_code: str
    unit_price: Money
    discount: Money = field(default_factory=lambda: Money(Decimal("0")))
    variant_id: uuid.UUID | None = None
    branch_id: uuid.UUID | None = None
    location_code: str = "default"

    @property
    def total(self) -> Money:
        return Money(self.unit_price.amount * self.quantity - self.discount.amount)


@dataclass
class Sale(AggregateRoot):
    cashier_id: uuid.UUID = field(default_factory=uuid.uuid4)
    idempotency_key: str = ""
    request_hash: str = ""
    payment_method: str = "cash"
    source: str = "pos"
    device_id: str = ""
    discount: Money = field(default_factory=lambda: Money(Decimal("0")))
    status: str = "pending_inventory"
    inventory_reservation_id: uuid.UUID | None = None
    items: list[SaleLine] = field(default_factory=list)

    @property
    def total(self) -> Money:
        return Money(sum((line.total.amount for line in self.items), Decimal("0")) - self.discount.amount)

    def validate(self) -> None:
        if not self.items:
            raise ValidationError("A sale must contain at least one product")
        if self.payment_method not in ("cash", "card", "transfer", "debt"):
            raise ValidationError("Unsupported payment_method")
        if self.discount.amount < 0:
            raise ValidationError("Sale discount cannot be negative")
        subtotal = sum((line.total.amount for line in self.items), Decimal("0"))
        if self.discount.amount > subtotal:
            raise ValidationError("Sale discount exceeds subtotal")
        if any(line.discount.amount < 0 or line.discount.amount > line.unit_price.amount * line.quantity for line in self.items):
            raise ValidationError("Line discount is outside the line total")
