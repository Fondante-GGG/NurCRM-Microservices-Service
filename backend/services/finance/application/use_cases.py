from __future__ import annotations
import uuid
from decimal import Decimal
from datetime import datetime, date, timezone
from typing import Protocol, List, Optional, Dict, Any

from libs.common.domain import Money
from libs.common.events import EventEnvelope, EventTypes
from libs.common.exceptions import NotFoundError, ShiftAlreadyOpenError, ConflictError, ValidationError
from backend.services.finance.domain.models import Accrual, SalaryPayout, CashShift, Material, InventoryMovement
from backend.services.finance.domain.repositories import (
    AccrualRepository,
    SalaryPayoutRepository,
    CashShiftRepository,
    WarehouseRepository,
)
from backend.services.finance.application.dto import (
    AccrualDTO,
    SalaryPayoutDTO,
    SalarySummaryDTO,
    CashShiftDTO,
)


class FinanceUnitOfWork(Protocol):
    accruals: AccrualRepository
    payouts: SalaryPayoutRepository
    shifts: CashShiftRepository
    warehouse: WarehouseRepository

    def __enter__(self) -> "FinanceUnitOfWork":
        ...

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        ...

    def commit(self) -> None:
        ...

    def record_outbox(self, event: EventEnvelope) -> None:
        ...


class CatalogClientPort(Protocol):
    def get_rate(self, company_id: uuid.UUID, service_id: uuid.UUID, master_id: Optional[uuid.UUID] = None) -> Decimal:
        ...


class ProcessAppointmentCompletedUseCase:
    """
    Idempotent accrual processor:
    Calculates master accrual = price * rate / 100 for completed appointment.
    Unique constraint on appointment_id prevents double accruals.
    """

    def __init__(self, uow: FinanceUnitOfWork, catalog_client: CatalogClientPort):
        self.uow = uow
        self.catalog = catalog_client

    def execute(
        self,
        company_id: uuid.UUID,
        appointment_id: uuid.UUID,
        master_id: uuid.UUID,
        price: Decimal,
        services: Optional[List[Dict[str, Any]]] = None,
    ) -> Optional[AccrualDTO]:
        with self.uow:
            existing = self.uow.accruals.get_by_appointment_id(appointment_id)
            if existing:
                # Already processed, idempotent return
                return AccrualDTO(
                    id=str(existing.id),
                    company_id=str(existing.company_id),
                    appointment_id=str(existing.appointment_id),
                    master_id=str(existing.master_id),
                    service_id=str(existing.service_id) if existing.service_id else None,
                    amount=existing.amount.amount,
                    percent=existing.percent,
                    created_at=existing.created_at.isoformat(),
                )

            # Query rate from catalog
            first_service_id = None
            rate_percent = Decimal("40.00")  # standard default rate
            if services and len(services) > 0:
                s_id = services[0].get("service_id") or services[0].get("id")
                if s_id:
                    first_service_id = uuid.UUID(str(s_id))
                    rate_percent = self.catalog.get_rate(company_id, first_service_id, master_id)

            accrual = Accrual.calculate(
                company_id=company_id,
                appointment_id=appointment_id,
                master_id=master_id,
                service_price=Money(price),
                percent=rate_percent,
                service_id=first_service_id,
            )
            self.uow.accruals.save(accrual)
            self.uow.commit()

            return AccrualDTO(
                id=str(accrual.id),
                company_id=str(accrual.company_id),
                appointment_id=str(accrual.appointment_id),
                master_id=str(accrual.master_id),
                service_id=str(accrual.service_id) if accrual.service_id else None,
                amount=accrual.amount.amount,
                percent=accrual.percent,
                created_at=accrual.created_at.isoformat(),
            )


class RegisterPayoutUseCase:
    def __init__(self, uow: FinanceUnitOfWork):
        self.uow = uow

    def execute(
        self,
        company_id: uuid.UUID,
        master_id: uuid.UUID,
        amount: Decimal,
        payout_date: Optional[date] = None,
        cashbox: str = "Основная касса",
        comment: Optional[str] = None,
    ) -> SalaryPayoutDTO:
        with self.uow:
            payout = SalaryPayout(
                id=uuid.uuid4(),
                company_id=company_id,
                master_id=master_id,
                amount=Money(amount),
                date=payout_date or date.today(),
                cashbox=cashbox,
                comment=comment,
            )
            self.uow.payouts.save(payout)

            event = EventEnvelope(
                type=EventTypes.FINANCE_PAYOUT_CREATED,
                company_id=str(company_id),
                data={
                    "payout_id": str(payout.id),
                    "master_id": str(payout.master_id),
                    "amount": str(payout.amount.amount),
                    "cashbox": payout.cashbox,
                    "date": payout.date.isoformat(),
                },
            )
            self.uow.record_outbox(event)
            self.uow.commit()

            return SalaryPayoutDTO(
                id=str(payout.id),
                company_id=str(payout.company_id),
                master_id=str(payout.master_id),
                amount=payout.amount.amount,
                date=payout.date.isoformat(),
                cashbox=payout.cashbox,
                comment=payout.comment,
                created_at=payout.created_at.isoformat(),
            )


class GetSalarySummaryUseCase:
    def __init__(self, uow: FinanceUnitOfWork):
        self.uow = uow

    def execute(self, company_id: uuid.UUID, master_id: Optional[uuid.UUID] = None) -> SalarySummaryDTO:
        with self.uow:
            accrued = self.uow.accruals.get_total_accrued(company_id, master_id)
            paid = self.uow.payouts.get_total_paid(company_id, master_id)
            balance = accrued - paid
            return SalarySummaryDTO(
                accrued_total=accrued,
                paid_total=paid,
                balance=balance,
            )


class OpenShiftUseCase:
    def __init__(self, uow: FinanceUnitOfWork):
        self.uow = uow

    def execute(self, company_id: uuid.UUID, user_id: uuid.UUID, cashbox: str, opening_cash: Decimal) -> CashShiftDTO:
        with self.uow:
            open_shift = self.uow.shifts.get_open_shift(company_id, cashbox)
            if open_shift:
                raise ShiftAlreadyOpenError(
                    f"A shift is already open for cashbox '{cashbox}'",
                    details={"existing_shift_id": str(open_shift.id)},
                )

            shift = CashShift(
                id=uuid.uuid4(),
                company_id=company_id,
                user_id=user_id,
                cashbox=cashbox,
                opening_cash=Money(opening_cash),
                status="open",
            )
            self.uow.shifts.save(shift)
            self.uow.commit()

            return CashShiftDTO(
                id=str(shift.id),
                company_id=str(shift.company_id),
                user_id=str(shift.user_id),
                cashbox=shift.cashbox,
                opening_cash=shift.opening_cash.amount,
                closing_cash=None,
                sales_total=shift.sales_total.amount,
                sales_count=shift.sales_count,
                status=shift.status,
                opened_at=shift.opened_at.isoformat(),
                closed_at=None,
            )


class CloseShiftUseCase:
    def __init__(self, uow: FinanceUnitOfWork):
        self.uow = uow

    def execute(self, company_id: uuid.UUID, shift_id: uuid.UUID, closing_cash: Decimal, sales_total: Decimal, sales_count: int) -> CashShiftDTO:
        with self.uow:
            shift = self.uow.shifts.get_by_id(company_id, shift_id)
            if not shift:
                raise NotFoundError(f"Shift {shift_id} not found")

            shift.close(
                closing_cash=Money(closing_cash),
                sales_total=Money(sales_total),
                sales_count=sales_count,
            )
            self.uow.shifts.save(shift)

            event = EventEnvelope(
                type=EventTypes.FINANCE_SHIFT_CLOSED,
                company_id=str(company_id),
                data={
                    "shift_id": str(shift.id),
                    "cashbox": shift.cashbox,
                    "sales_total": str(shift.sales_total.amount),
                    "sales_count": shift.sales_count,
                    "closing_cash": str(shift.closing_cash.amount if shift.closing_cash else "0.00"),
                },
            )
            self.uow.record_outbox(event)
            self.uow.commit()

            return CashShiftDTO(
                id=str(shift.id),
                company_id=str(shift.company_id),
                user_id=str(shift.user_id),
                cashbox=shift.cashbox,
                opening_cash=shift.opening_cash.amount,
                closing_cash=shift.closing_cash.amount if shift.closing_cash else None,
                sales_total=shift.sales_total.amount,
                sales_count=shift.sales_count,
                status=shift.status,
                opened_at=shift.opened_at.isoformat(),
                closed_at=shift.closed_at.isoformat() if shift.closed_at else None,
            )
