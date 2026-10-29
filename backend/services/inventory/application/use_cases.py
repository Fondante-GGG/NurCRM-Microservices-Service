from decimal import Decimal
from typing import Dict, List, Protocol
import uuid

from backend.services.inventory.domain.models import StockBalance


class InventoryRepository(Protocol):
    def list_stock(
        self,
        company_id: uuid.UUID,
        product_id: uuid.UUID | None = None,
        branch_id: uuid.UUID | None = None,
    ) -> List[StockBalance]:
        ...

    def reserve(
        self,
        company_id: uuid.UUID,
        idempotency_key: str,
        items: List[Dict],
    ) -> uuid.UUID:
        ...

    def commit_reservation(self, company_id: uuid.UUID, reservation_id: uuid.UUID) -> None:
        ...

    def release_reservation(self, company_id: uuid.UUID, reservation_id: uuid.UUID) -> None:
        ...

    def adjust_stock(
        self,
        company_id: uuid.UUID,
        product_id: uuid.UUID,
        variant_id: uuid.UUID | None,
        branch_id: uuid.UUID | None,
        location_code: str,
        quantity: Decimal,
        movement_type: str,
        source_key: str,
    ) -> StockBalance:
        ...


class ReserveStockUseCase:
    def __init__(self, repository: InventoryRepository):
        self.repository = repository

    def execute(self, company_id: uuid.UUID, idempotency_key: str, items: List[Dict]) -> uuid.UUID:
        return self.repository.reserve(company_id, idempotency_key, items)


class CommitReservationUseCase:
    def __init__(self, repository: InventoryRepository):
        self.repository = repository

    def execute(self, company_id: uuid.UUID, reservation_id: uuid.UUID) -> None:
        self.repository.commit_reservation(company_id, reservation_id)


class ReleaseReservationUseCase:
    def __init__(self, repository: InventoryRepository):
        self.repository = repository

    def execute(self, company_id: uuid.UUID, reservation_id: uuid.UUID) -> None:
        self.repository.release_reservation(company_id, reservation_id)
