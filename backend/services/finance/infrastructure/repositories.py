from typing import Optional, List
import uuid
from decimal import Decimal
from django.db.models import Sum

from libs.common.domain import Money
from backend.services.finance.domain.models import Accrual, SalaryPayout, CashShift, Material, InventoryMovement
from backend.services.finance.domain.repositories import (
    AccrualRepository,
    SalaryPayoutRepository,
    CashShiftRepository,
    WarehouseRepository,
)
from backend.services.finance.infrastructure.models import (
    AccrualModel,
    SalaryPayoutModel,
    CashShiftModel,
    WarehouseMaterialModel,
    InventoryMovementModel,
)


class DjangoAccrualRepository(AccrualRepository):
    def _to_domain(self, m: AccrualModel) -> Accrual:
        return Accrual(
            id=m.id,
            company_id=m.company_id,
            appointment_id=m.appointment_id,
            master_id=m.master_id,
            service_id=m.service_id,
            amount=Money(m.amount),
            percent=m.percent,
            created_at=m.created_at,
        )

    def get_by_appointment_id(self, appointment_id: uuid.UUID) -> Optional[Accrual]:
        try:
            m = AccrualModel.objects.get(appointment_id=appointment_id)
            return self._to_domain(m)
        except AccrualModel.DoesNotExist:
            return None

    def list_by_master(self, company_id: uuid.UUID, master_id: uuid.UUID) -> List[Accrual]:
        qs = AccrualModel.objects.filter(company_id=company_id, master_id=master_id).order_by("-created_at")
        return [self._to_domain(m) for m in qs]

    def list_by_company(self, company_id: uuid.UUID) -> List[Accrual]:
        qs = AccrualModel.objects.filter(company_id=company_id).order_by("-created_at")
        return [self._to_domain(m) for m in qs]

    def get_total_accrued(self, company_id: uuid.UUID, master_id: Optional[uuid.UUID] = None) -> Decimal:
        qs = AccrualModel.objects.filter(company_id=company_id)
        if master_id:
            qs = qs.filter(master_id=master_id)
        total = qs.aggregate(Sum("amount"))["amount__sum"]
        return total if total is not None else Decimal("0.00")

    def save(self, accrual: Accrual) -> None:
        AccrualModel.objects.update_or_create(
            appointment_id=accrual.appointment_id,
            defaults={
                "id": accrual.id,
                "company_id": accrual.company_id,
                "master_id": accrual.master_id,
                "service_id": accrual.service_id,
                "amount": accrual.amount.amount,
                "percent": accrual.percent,
            },
        )


class DjangoSalaryPayoutRepository(SalaryPayoutRepository):
    def _to_domain(self, m: SalaryPayoutModel) -> SalaryPayout:
        return SalaryPayout(
            id=m.id,
            company_id=m.company_id,
            master_id=m.master_id,
            amount=Money(m.amount),
            date=m.date,
            cashbox=m.cashbox,
            comment=m.comment,
            created_at=m.created_at,
        )

    def list_by_master(self, company_id: uuid.UUID, master_id: uuid.UUID) -> List[SalaryPayout]:
        qs = SalaryPayoutModel.objects.filter(company_id=company_id, master_id=master_id).order_by("-date")
        return [self._to_domain(m) for m in qs]

    def list_by_company(self, company_id: uuid.UUID) -> List[SalaryPayout]:
        qs = SalaryPayoutModel.objects.filter(company_id=company_id).order_by("-date")
        return [self._to_domain(m) for m in qs]

    def get_total_paid(self, company_id: uuid.UUID, master_id: Optional[uuid.UUID] = None) -> Decimal:
        qs = SalaryPayoutModel.objects.filter(company_id=company_id)
        if master_id:
            qs = qs.filter(master_id=master_id)
        total = qs.aggregate(Sum("amount"))["amount__sum"]
        return total if total is not None else Decimal("0.00")

    def save(self, payout: SalaryPayout) -> None:
        SalaryPayoutModel.objects.update_or_create(
            id=payout.id,
            defaults={
                "company_id": payout.company_id,
                "master_id": payout.master_id,
                "amount": payout.amount.amount,
                "date": payout.date,
                "cashbox": payout.cashbox,
                "comment": payout.comment,
            },
        )


class DjangoCashShiftRepository(CashShiftRepository):
    def _to_domain(self, m: CashShiftModel) -> CashShift:
        closing = Money(m.closing_cash) if m.closing_cash is not None else None
        return CashShift(
            id=m.id,
            company_id=m.company_id,
            user_id=m.user_id,
            cashbox=m.cashbox,
            opening_cash=Money(m.opening_cash),
            closing_cash=closing,
            sales_total=Money(m.sales_total),
            sales_count=m.sales_count,
            status=m.status,
            opened_at=m.opened_at,
            closed_at=m.closed_at,
        )

    def get_open_shift(self, company_id: uuid.UUID, cashbox: str) -> Optional[CashShift]:
        try:
            m = CashShiftModel.objects.get(company_id=company_id, cashbox=cashbox, status="open")
            return self._to_domain(m)
        except CashShiftModel.DoesNotExist:
            return None

    def get_by_id(self, company_id: uuid.UUID, shift_id: uuid.UUID) -> Optional[CashShift]:
        try:
            m = CashShiftModel.objects.get(company_id=company_id, id=shift_id)
            return self._to_domain(m)
        except CashShiftModel.DoesNotExist:
            return None

    def list_by_company(self, company_id: uuid.UUID) -> List[CashShift]:
        qs = CashShiftModel.objects.filter(company_id=company_id).order_by("-opened_at")
        return [self._to_domain(m) for m in qs]

    def save(self, shift: CashShift) -> None:
        closing = shift.closing_cash.amount if shift.closing_cash else None
        CashShiftModel.objects.update_or_create(
            id=shift.id,
            defaults={
                "company_id": shift.company_id,
                "user_id": shift.user_id,
                "cashbox": shift.cashbox,
                "opening_cash": shift.opening_cash.amount,
                "closing_cash": closing,
                "sales_total": shift.sales_total.amount,
                "sales_count": shift.sales_count,
                "status": shift.status,
                "closed_at": shift.closed_at,
            },
        )


class DjangoWarehouseRepository(WarehouseRepository):
    def _to_domain(self, m: WarehouseMaterialModel) -> Material:
        return Material(
            id=m.id,
            company_id=m.company_id,
            name=m.name,
            unit=m.unit,
            current_stock=m.current_stock,
            cost_price=Money(m.cost_price),
            created_at=m.created_at,
        )

    def get_material_by_id(self, company_id: uuid.UUID, material_id: uuid.UUID) -> Optional[Material]:
        try:
            m = WarehouseMaterialModel.objects.get(company_id=company_id, id=material_id)
            return self._to_domain(m)
        except WarehouseMaterialModel.DoesNotExist:
            return None

    def list_materials(self, company_id: uuid.UUID) -> List[Material]:
        qs = WarehouseMaterialModel.objects.filter(company_id=company_id)
        return [self._to_domain(m) for m in qs]

    def save_material(self, material: Material) -> None:
        WarehouseMaterialModel.objects.update_or_create(
            id=material.id,
            defaults={
                "company_id": material.company_id,
                "name": material.name,
                "unit": material.unit,
                "current_stock": material.current_stock,
                "cost_price": material.cost_price.amount,
            },
        )

    def record_movement(self, movement: InventoryMovement) -> None:
        InventoryMovementModel.objects.create(
            id=movement.id,
            company_id=movement.company_id,
            material_id=movement.material_id,
            movement_type=movement.movement_type,
            quantity=movement.quantity,
            price=movement.price.amount,
            reason=movement.reason,
        )
