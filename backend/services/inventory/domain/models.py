from dataclasses import dataclass
from decimal import Decimal
import uuid

from libs.common.exceptions import ConflictError, ValidationError


@dataclass
class StockBalance:
    id: uuid.UUID
    company_id: uuid.UUID
    product_id: uuid.UUID
    quantity: Decimal
    reserved: Decimal = Decimal("0")
    variant_id: uuid.UUID | None = None
    branch_id: uuid.UUID | None = None
    location_code: str = "default"

    @property
    def available(self) -> Decimal:
        return self.quantity - self.reserved

    def reserve(self, amount: Decimal) -> None:
        self._validate_amount(amount)
        if self.available < amount:
            raise ConflictError(
                "Insufficient stock",
                code="stock_insufficient",
                details={"available": str(self.available), "requested": str(amount)},
            )
        self.reserved += amount

    def release(self, amount: Decimal) -> None:
        self._validate_amount(amount)
        if self.reserved < amount:
            raise ConflictError("Reservation exceeds reserved stock", code="reservation_mismatch")
        self.reserved -= amount

    def consume(self, amount: Decimal) -> None:
        self._validate_amount(amount)
        if self.reserved < amount or self.quantity < amount:
            raise ConflictError("Reserved stock is no longer available", code="reservation_mismatch")
        self.reserved -= amount
        self.quantity -= amount

    def adjust(self, delta: Decimal) -> None:
        if delta == 0:
            raise ValidationError("Stock adjustment cannot be zero")
        if self.available + delta < 0:
            raise ConflictError(
                "Adjustment would make available stock negative",
                code="stock_insufficient",
                details={"available": str(self.available), "adjustment": str(delta)},
            )
        self.quantity += delta

    @staticmethod
    def _validate_amount(amount: Decimal) -> None:
        if amount <= 0:
            raise ValidationError("Stock quantity must be greater than zero")
