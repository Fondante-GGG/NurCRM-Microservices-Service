from typing import Optional, List, Protocol
import uuid
from decimal import Decimal
from datetime import date
from backend.services.finance.domain.models import Accrual, SalaryPayout, CashShift, Material, InventoryMovement


class AccrualRepository(Protocol):
    def get_by_appointment_id(self, appointment_id: uuid.UUID) -> Optional[Accrual]:
        ...

    def list_by_master(self, company_id: uuid.UUID, master_id: uuid.UUID) -> List[Accrual]:
        ...

    def list_by_company(self, company_id: uuid.UUID) -> List[Accrual]:
        ...

    def get_total_accrued(self, company_id: uuid.UUID, master_id: Optional[uuid.UUID] = None) -> Decimal:
        ...

    def save(self, accrual: Accrual) -> None:
        ...


class SalaryPayoutRepository(Protocol):
    def list_by_master(self, company_id: uuid.UUID, master_id: uuid.UUID) -> List[SalaryPayout]:
        ...

    def list_by_company(self, company_id: uuid.UUID) -> List[SalaryPayout]:
        ...

    def get_total_paid(self, company_id: uuid.UUID, master_id: Optional[uuid.UUID] = None) -> Decimal:
        ...

    def save(self, payout: SalaryPayout) -> None:
        ...


class CashShiftRepository(Protocol):
    def get_open_shift(self, company_id: uuid.UUID, cashbox: str) -> Optional[CashShift]:
        ...

    def get_by_id(self, company_id: uuid.UUID, shift_id: uuid.UUID) -> Optional[CashShift]:
        ...

    def list_by_company(self, company_id: uuid.UUID) -> List[CashShift]:
        ...

    def save(self, shift: CashShift) -> None:
        ...


class WarehouseRepository(Protocol):
    def get_material_by_id(self, company_id: uuid.UUID, material_id: uuid.UUID) -> Optional[Material]:
        ...

    def list_materials(self, company_id: uuid.UUID) -> List[Material]:
        ...

    def save_material(self, material: Material) -> None:
        ...

    def record_movement(self, movement: InventoryMovement) -> None:
        ...
