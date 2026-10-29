import uuid
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

from libs.common.domain import Money
from backend.services.rent.domain.models import (
    Charge,
    Lease,
    PayrollKRCalculator,
    ReconciliationActBuilder,
    Tenant,
    Unit,
    allocate_payment_fifo,
)


class RentBillingUseCase:
    """Use case for monthly recurring billing, FIFO payment allocation and penalty calculation."""

    @staticmethod
    def generate_monthly_charges(
        company_id: uuid.UUID,
        branch_id: uuid.UUID,
        active_leases: List[Lease],
        period: str,  # e.g. "2026-11"
        due_day: int = 5,
    ) -> List[Charge]:
        """
        Фоновая генерация 1-го числа каждого месяца по действующим договорам.
        Идемпотентна: создает начисления со сроком оплаты из договора.
        """
        charges: List[Charge] = []
        year, month = map(int, period.split("-"))

        for lease in active_leases:
            if lease.status != "active":
                continue
            
            charge_due_date = date(year, month, lease.payment_day or due_day)
            charge = Charge(
                id=uuid.uuid4(),
                company_id=company_id,
                branch_id=branch_id,
                lease_id=lease.id,
                tenant_id=lease.tenant_id,
                type="rent",
                period=period,
                amount=lease.monthly_rent,
                due_date=charge_due_date,
                is_paid=False,
            )
            charges.append(charge)
        return charges

    @staticmethod
    def process_tenant_payment(
        payment_amount: Money,
        unpaid_charges: List[Charge],
    ) -> Tuple[List[Tuple[Charge, Money]], Money]:
        """
        Разнесение оплаты по методу FIFO:
        Сначала закрываются самые старые начисления, переплата остается авансом.
        """
        allocations = allocate_payment_fifo(payment_amount, unpaid_charges)
        total_allocated = sum((alloc[1].amount for alloc in allocations), Decimal("0.00"))
        excess_advance = Money(max(Decimal("0.00"), payment_amount.amount - total_allocated))
        return allocations, excess_advance

    @staticmethod
    def calculate_penalties(
        lease: Lease,
        overdue_charges: List[Charge],
        current_date: date,
    ) -> List[Dict[str, Any]]:
        """
        Начисление пени с 1-го дня просрочки:
        Пеня = Долг × ставка в день × дней просрочки
        """
        penalty_details = []
        for charge in overdue_charges:
            if not charge.is_paid and charge.due_date < current_date:
                days_overdue = (current_date - charge.due_date).days
                debt = charge.remaining_due
                penalty = lease.calculate_penalty(debt, days_overdue)
                penalty_details.append({
                    "charge_id": charge.id,
                    "period": charge.period,
                    "debt": debt.amount,
                    "days_overdue": days_overdue,
                    "daily_rate_pct": lease.penalty_pct,
                    "penalty_amount": penalty.amount,
                })
        return penalty_details
