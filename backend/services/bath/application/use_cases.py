import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

from libs.common.domain import Money
from backend.services.bath.domain.models import (
    BarItem,
    DebtLimitExceededError,
    DebtOutstandingError,
    EntryTariff,
    Locker,
    MasterService,
    Visit,
    VisitItem,
)


class BathSessionUseCase:
    """Use case coordinating open bracelet visits, bar sales, master services and checkout."""

    @staticmethod
    def start_visit(
        company_id: uuid.UUID,
        branch_id: uuid.UUID,
        locker: Locker,
        tariff: EntryTariff,
        client_id: Optional[uuid.UUID] = None,
        group_id: Optional[uuid.UUID] = None,
        pay_entry_now: bool = False,
    ) -> Tuple[Visit, Optional[Money]]:
        if locker.is_broken:
            raise ValueError(f"Locker {locker.code} is under repair")
        
        visit = Visit(
            id=uuid.uuid4(),
            company_id=company_id,
            branch_id=branch_id,
            locker_id=locker.id,
            tariff_id=tariff.id,
            client_id=client_id,
            group_id=group_id,
            started_at=datetime.now(timezone.utc),
            status="open",
        )

        entry_item = visit.add_item(
            source="entry",
            name=f"Вход: {tariff.name}",
            price=tariff.price,
            qty=1,
            cost=Money(Decimal("0.00")),
        )

        entry_due = tariff.price if pay_entry_now else None
        return visit, entry_due

    @staticmethod
    def record_bar_order(
        visit: Visit,
        bar_item: BarItem,
        qty: int,
        debt_limit: Money,
        current_tariff: EntryTariff,
        now: datetime,
        can_bypass_limit: bool = False,
        employee_id: Optional[uuid.UUID] = None,
    ) -> Tuple[VisitItem, Optional[str]]:
        # 1. Сначала проверяем физический остаток на складе
        stock_alert = bar_item.deduct_stock(qty)

        # 2. Затем проверяем лимит долга
        order_cost = Money(bar_item.price.amount * Decimal(qty))
        current_debt = visit.calculate_total_debt(now, current_tariff)

        if (current_debt + order_cost) > debt_limit and not can_bypass_limit:
            # Возвращаем списанный остаток при отказе по лимиту
            if bar_item.stock is not None:
                bar_item.stock += qty
            raise DebtLimitExceededError(
                f"Order of {order_cost.amount} KGS exceeds allowed limit ({debt_limit.amount} KGS). Current debt: {current_debt.amount} KGS."
            )

        item = visit.add_item(
            source="bar",
            name=bar_item.name,
            price=bar_item.price,
            qty=qty,
            cost=bar_item.cost,
            employee_id=employee_id,
        )
        return item, stock_alert

    @staticmethod
    def record_master_service(
        visit: Visit,
        service: MasterService,
        master_id: uuid.UUID,
        master_pct: Decimal,
        debt_limit: Money,
        current_tariff: EntryTariff,
        now: datetime,
        can_bypass_limit: bool = False,
    ) -> Tuple[VisitItem, Money]:
        service_cost = service.price
        current_debt = visit.calculate_total_debt(now, current_tariff)

        if (current_debt + service_cost) > debt_limit and not can_bypass_limit:
            raise DebtLimitExceededError(
                f"Service {service.name} ({service_cost.amount} KGS) exceeds debt limit. Current debt: {current_debt.amount} KGS."
            )

        master_accrual = MasterService.calculate_commission(
            price=service.price,
            pct=master_pct,
        )

        item = visit.add_item(
            source="service",
            name=service.name,
            price=service.price,
            qty=1,
            cost=Money(Decimal("0.00")),
            employee_id=master_id,
        )
        return item, master_accrual

    @staticmethod
    def checkout_guest(
        visit: Visit,
        tariff: EntryTariff,
        paid_amount: Money,
        now: datetime,
        closed_by: uuid.UUID,
        allow_debt: bool = False,
        old_client_debt: Optional[Money] = None,
    ) -> Dict[str, Any]:
        overage = visit.calculate_overage_charge(now, tariff)
        if overage.amount > 0:
            visit.add_item(
                source="time",
                name=f"Доплата за время ({tariff.extra_per_hour.amount} с/ч)",
                price=overage,
                qty=1,
            )

        total_visit_debt = visit.calculate_total_debt(now, tariff)
        grand_total = total_visit_debt
        if old_client_debt and old_client_debt.amount > 0:
            grand_total = grand_total + old_client_debt

        visit.close_visit(
            paid_amount=paid_amount,
            total_debt=grand_total,
            closed_by=closed_by,
            allow_debt=allow_debt,
        )

        remaining_debt = Money(max(Decimal("0.00"), grand_total.amount - paid_amount.amount))

        return {
            "visit_id": visit.id,
            "status": visit.status,
            "total_due": grand_total.amount,
            "paid_amount": paid_amount.amount,
            "remaining_debt": remaining_debt.amount,
            "locker_released": True,
        }
