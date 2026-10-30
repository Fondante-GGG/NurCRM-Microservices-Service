import math
import uuid
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

from libs.common.domain import AggregateRoot, Entity, Money


@dataclass
class Unit(Entity):
    company_id: uuid.UUID
    branch_id: uuid.UUID
    number: str
    floor: int
    area_sqm: Decimal
    rate_per_sqm: Money
    unit_type_id: Optional[uuid.UUID] = None
    reservation_until: Optional[date] = None
    reservation_who: Optional[str] = None

    def calculate_monthly_rent(self) -> Money:
        return Money((self.area_sqm * self.rate_per_sqm.amount).quantize(Decimal("0.01")))

    def is_available(self, for_date: date) -> bool:
        if self.reservation_until and self.reservation_until >= for_date:
            return False
        return True


@dataclass
class Tenant(Entity):
    company_id: uuid.UUID
    name: str
    legal_form: str  # 'ИП', 'ОсОО', 'физлицо'
    inn: str = ""
    contact_person: str = ""
    passport: str = ""
    phone: str = ""
    activity_type: str = ""


@dataclass
class Lease(AggregateRoot):
    branch_id: uuid.UUID = field(default_factory=uuid.uuid4)
    tenant_id: uuid.UUID = field(default_factory=uuid.uuid4)
    unit_ids: List[uuid.UUID] = field(default_factory=list)
    number: str = ""
    start_date: date = field(default_factory=date.today)
    end_date: date = field(default_factory=date.today)
    monthly_rent: Money = field(default_factory=lambda: Money(Decimal("0.00")))
    payment_day: int = 5
    deposit: Money = field(default_factory=lambda: Money(Decimal("0.00")))
    penalty_pct: Decimal = Decimal("0.1")  # 0.1% в день
    indexation_pct: Decimal = Decimal("0.0")
    utilities: Money = field(default_factory=lambda: Money(Decimal("0.00")))
    status: str = "active"  # 'active', 'draft', 'expiring', 'expired'
    contract_text_snapshot: str = ""
    template_id: Optional[uuid.UUID] = None

    def calculate_penalty(self, debt: Money, days_overdue: int) -> Money:
        """
        Формула из ТЗ:
        Пеня = Долг × ставка в день × дней просрочки
        """
        if days_overdue <= 0 or debt.amount <= 0:
            return Money(Decimal("0.00"))
        
        penalty_amount = (
            debt.amount * (self.penalty_pct / Decimal("100.00")) * Decimal(days_overdue)
        ).quantize(Decimal("0.01"))
        return Money(penalty_amount)

    def is_expired(self, current_date: date) -> bool:
        return current_date > self.end_date

    def days_until_expiry(self, current_date: date) -> int:
        return (self.end_date - current_date).days


@dataclass
class Charge:
    id: uuid.UUID
    company_id: uuid.UUID
    branch_id: uuid.UUID
    lease_id: uuid.UUID
    tenant_id: uuid.UUID
    type: str  # 'rent', 'penalty', 'fine', 'utility'
    period: str  # e.g. "2026-10"
    amount: Money
    due_date: date
    is_paid: bool = False
    paid_amount: Money = field(default_factory=lambda: Money(Decimal("0.00")))

    @property
    def remaining_due(self) -> Money:
        return self.amount - self.paid_amount


def allocate_payment_fifo(
    payment_amount: Money,
    unpaid_charges: List[Charge],
) -> List[Tuple[Charge, Money]]:
    """
    Разнесение оплаты по методу FIFO:
    Оплата сначала закрывает самые старые начисления, потом текущий месяц.
    """
    allocations: List[Tuple[Charge, Money]] = []
    remaining_payment = payment_amount.amount

    # Сортируем по сроку оплаты (самые старые первыми)
    sorted_charges = sorted(unpaid_charges, key=lambda c: (c.due_date, c.period))

    for charge in sorted_charges:
        if remaining_payment <= Decimal("0.00"):
            break
        charge_need = charge.remaining_due.amount
        if charge_need <= Decimal("0.00"):
            continue

        allocate_sum = min(remaining_payment, charge_need)
        allocated_money = Money(allocate_sum)
        charge.paid_amount = charge.paid_amount + allocated_money
        if charge.paid_amount >= charge.amount:
            charge.is_paid = True

        remaining_payment -= allocate_sum
        allocations.append((charge, allocated_money))

    return allocations


class PayrollKRCalculator:
    """
    Расчет зарплаты по ставкам Кыргызской Республики (из ТЗ):
    Соцфонд работника = 10%
    Подоходный налог (ПН) = (Начислено - Соцфонд) × 10%
    На руки = Начислено - Соцфонд - ПН
    Аванс = Оклад × 40%, округление до 100 сом
    К выплате = На руки - Аванс
    Взнос работодателя = Начислено × 17.25%
    """

    @staticmethod
    def calculate(
        base_salary: Money,
        bonus: Money = Money(Decimal("0.00")),
    ) -> Dict[str, Money]:
        gross = base_salary + bonus

        # Соцфонд работника 10%
        social_fund_worker = Money((gross.amount * Decimal("0.10")).quantize(Decimal("0.01")))

        # Подоходный налог 10% от базы (gross - social_fund)
        taxable_base = gross - social_fund_worker
        income_tax = Money((taxable_base.amount * Decimal("0.10")).quantize(Decimal("0.01")))

        # На руки
        net_salary = gross - social_fund_worker - income_tax

        # Аванс 40% от оклада, округление до 100 сом
        raw_advance = base_salary.amount * Decimal("0.40")
        rounded_advance = Decimal(round(raw_advance / Decimal(100))) * Decimal(100)
        advance = Money(rounded_advance.quantize(Decimal("0.01")))

        # К окончательной выплате
        payout = net_salary - advance

        # Взнос работодателя в Соцфонд 17.25%
        employer_contribution = Money((gross.amount * Decimal("0.1725")).quantize(Decimal("0.01")))

        return {
            "gross": gross,
            "social_fund_worker": social_fund_worker,
            "income_tax": income_tax,
            "net_salary": net_salary,
            "advance": advance,
            "payout": payout,
            "employer_contribution": employer_contribution,
            "total_company_cost": gross + employer_contribution,
        }


class ReconciliationActBuilder:
    """
    Генератор акта сверки взаимных расчетов:
    Сальдо на начало + Обороты по дебету (начисления) - Обороты по кредиту (оплаты) = Сальдо на конец.
    """

    @staticmethod
    def build_act(
        tenant: Tenant,
        period_from: date,
        period_to: date,
        opening_balance: Money,
        debit_items: List[Dict[str, Any]],  # charges: {date, doc, amount}
        credit_items: List[Dict[str, Any]],  # payments: {date, doc, amount}
    ) -> Dict[str, Any]:
        rows: List[Dict[str, Any]] = []

        # Объединяем и хронологически сортируем
        all_events = []
        for d in debit_items:
            all_events.append({
                "date": d["date"],
                "doc": d.get("doc", "Начисление аренды / штраф"),
                "debit": d["amount"].amount,
                "credit": Decimal("0.00"),
            })
        for c in credit_items:
            all_events.append({
                "date": c["date"],
                "doc": c.get("doc", "Оплата"),
                "debit": Decimal("0.00"),
                "credit": c["amount"].amount,
            })

        all_events.sort(key=lambda x: x["date"])

        running_balance = opening_balance.amount
        total_debit = Decimal("0.00")
        total_credit = Decimal("0.00")

        for event in all_events:
            total_debit += event["debit"]
            total_credit += event["credit"]
            running_balance += (event["debit"] - event["credit"])
            rows.append({
                "date": str(event["date"]),
                "document": event["doc"],
                "debit": float(event["debit"]),
                "credit": float(event["credit"]),
                "balance": float(running_balance),
            })

        closing_balance = Money(running_balance)

        return {
            "tenant_id": tenant.id,
            "tenant_name": tenant.name,
            "period_from": str(period_from),
            "period_to": str(period_to),
            "opening_balance": opening_balance.amount,
            "total_debit": total_debit,
            "total_credit": total_credit,
            "closing_balance": closing_balance.amount,
            "rows": rows,
            "conclusion_phrase": (
                f"Задолженность в пользу Арендодателя составляет {closing_balance.amount} сом."
                if closing_balance.amount > 0
                else f"Задолженность отсутствует (переплата {abs(closing_balance.amount)} сом)."
            ),
        }
