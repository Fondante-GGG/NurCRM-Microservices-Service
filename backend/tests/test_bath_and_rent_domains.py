import math
import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
import pytest

from libs.common.domain import Money
from backend.services.bath.domain.models import (
    BarItem,
    DebtLimitExceededError,
    DebtOutstandingError,
    EntryTariff,
    InsufficientStockError,
    Locker,
    MasterService,
    Visit,
)
from backend.services.bath.application.use_cases import BathSessionUseCase
from backend.services.rent.domain.models import (
    Charge,
    Lease,
    PayrollKRCalculator,
    ReconciliationActBuilder,
    Tenant,
    Unit,
    allocate_payment_fifo,
)
from backend.services.rent.application.use_cases import RentBillingUseCase


# ==============================================================================
# TESTS FOR KEZEK BATH & SAUNA MODE
# ==============================================================================

def test_bath_entry_and_overage_calculation():
    """Тест тарифа входа и доплаты за перерасход времени (3 ч + 100 с/ч)."""
    company_id = uuid.uuid4()
    branch_id = uuid.uuid4()
    locker = Locker(
        id=uuid.uuid4(),
        company_id=company_id,
        branch_id=branch_id,
        category_id=uuid.uuid4(),
        number=12,
        code="М12",
    )
    tariff = EntryTariff(
        id=uuid.uuid4(),
        company_id=company_id,
        branch_id=branch_id,
        name="Стандартный вход",
        price=Money(Decimal("500.00")),
        included_hours=3,
        extra_per_hour=Money(Decimal("100.00")),
    )

    visit, _ = BathSessionUseCase.start_visit(
        company_id=company_id,
        branch_id=branch_id,
        locker=locker,
        tariff=tariff,
    )

    # 1. Гость пробыл 2 часа 45 мин — перерасхода нет
    now_within = visit.started_at + timedelta(hours=2, minutes=45)
    overage = visit.calculate_overage_charge(now_within, tariff)
    assert overage.amount == Decimal("0.00")

    # 2. Пример из ТЗ: внутри 3 ч 35 мин → начался 4-й час → доплата 100 сом
    now_3h35 = visit.started_at + timedelta(hours=3, minutes=35)
    overage = visit.calculate_overage_charge(now_3h35, tariff)
    assert overage.amount == Decimal("100.00")

    # 3. Внутри 4 ч 10 мин → перерасход 1 ч 10 мин → округление вверх = 2 часа → 200 сом
    now_4h10 = visit.started_at + timedelta(hours=4, minutes=10)
    overage_2h = visit.calculate_overage_charge(now_4h10, tariff)
    assert overage_2h.amount == Decimal("200.00")


def test_bath_debt_limit_and_bar_stock():
    """Тест контроля лимита долга и атомарного списания остатков бара."""
    company_id = uuid.uuid4()
    branch_id = uuid.uuid4()
    locker = Locker(
        id=uuid.uuid4(),
        company_id=company_id,
        branch_id=branch_id,
        category_id=uuid.uuid4(),
        number=11,
        code="М11",
    )
    tariff = EntryTariff(
        id=uuid.uuid4(),
        company_id=company_id,
        branch_id=branch_id,
        name="Вход",
        price=Money(Decimal("300.00")),
    )
    visit, _ = BathSessionUseCase.start_visit(company_id, branch_id, locker, tariff)

    bar_item = BarItem(
        id=uuid.uuid4(),
        company_id=company_id,
        branch_id=branch_id,
        name="Пиво крафтовое",
        price=Money(Decimal("180.00")),
        cost=Money(Decimal("95.00")),
        stock=4,
    )

    # Проверка маржи из ТЗ: (180 - 95) = 85 с, ~47.22%
    assert bar_item.profit_per_unit.amount == Decimal("85.00")
    assert bar_item.margin_pct == Decimal("47.22")

    now = datetime.now(timezone.utc)
    debt_limit = Money(Decimal("1000.00"))

    # Заказ 2 бутылок пива: 300 (вход) + 360 (пиво) = 660 <= 1000 — проходит
    item, alert = BathSessionUseCase.record_bar_order(
        visit=visit,
        bar_item=bar_item,
        qty=2,
        debt_limit=debt_limit,
        current_tariff=tariff,
        now=now,
    )
    assert item.name == "Пиво крафтовое"
    assert bar_item.stock == 2
    assert alert == "low_stock"  # остаток <= 5

    # Попытка заказать еще 5 бутылок при остатке 2 — InsufficientStockError
    with pytest.raises(InsufficientStockError):
        BathSessionUseCase.record_bar_order(
            visit=visit,
            bar_item=bar_item,
            qty=5,
            debt_limit=debt_limit,
            current_tariff=tariff,
            now=now,
        )

    # Попытка заказать на сумму, превышающую лимит 1000 без права оверрайда
    expensive_item = BarItem(
        id=uuid.uuid4(),
        company_id=company_id,
        branch_id=branch_id,
        name="Коньяк элитный",
        price=Money(Decimal("500.00")),
        cost=Money(Decimal("300.00")),
        stock=10,
    )
    # Текущий долг 660 + 500 = 1160 > 1000
    with pytest.raises(DebtLimitExceededError):
        BathSessionUseCase.record_bar_order(
            visit=visit,
            bar_item=expensive_item,
            qty=1,
            debt_limit=debt_limit,
            current_tariff=tariff,
            now=now,
            can_bypass_limit=False,
        )


def test_bath_master_commission_and_checkout():
    """Тест начисления мастеру за услугу и контроля долга на выходе."""
    company_id = uuid.uuid4()
    branch_id = uuid.uuid4()
    locker = Locker(
        id=uuid.uuid4(),
        company_id=company_id,
        branch_id=branch_id,
        category_id=uuid.uuid4(),
        number=22,
        code="М22",
    )
    tariff = EntryTariff(
        id=uuid.uuid4(),
        company_id=company_id,
        branch_id=branch_id,
        name="Вход",
        price=Money(Decimal("500.00")),
    )
    visit, _ = BathSessionUseCase.start_visit(company_id, branch_id, locker, tariff)

    # Услуга из ТЗ: массаж 2000 с, 30% мастера → 600 с
    master_id = uuid.uuid4()
    service = MasterService(
        id=uuid.uuid4(),
        company_id=company_id,
        branch_id=branch_id,
        name="Массаж классический",
        price=Money(Decimal("2000.00")),
    )

    item, commission = BathSessionUseCase.record_master_service(
        visit=visit,
        service=service,
        master_id=master_id,
        master_pct=Decimal("30.00"),
        debt_limit=Money(Decimal("5000.00")),
        current_tariff=tariff,
        now=datetime.now(timezone.utc),
    )
    assert commission.amount == Decimal("600.00")

    # Итоговый долг: 500 (вход) + 2000 (массаж) = 2500 сом
    total_debt = visit.calculate_total_debt(datetime.now(timezone.utc), tariff)
    assert total_debt.amount == Decimal("2500.00")

    # Попытка отпустить гостя без оплаты (0 сом) без права "долг"
    with pytest.raises(DebtOutstandingError):
        BathSessionUseCase.checkout_guest(
            visit=visit,
            tariff=tariff,
            paid_amount=Money(Decimal("0.00")),
            now=datetime.now(timezone.utc),
            closed_by=uuid.uuid4(),
            allow_debt=False,
        )

    # Успешная оплата на выходе
    result = BathSessionUseCase.checkout_guest(
        visit=visit,
        tariff=tariff,
        paid_amount=Money(Decimal("2500.00")),
        now=datetime.now(timezone.utc),
        closed_by=uuid.uuid4(),
        allow_debt=False,
    )
    assert result["status"] == "paid"
    assert result["remaining_debt"] == Decimal("0.00")
    assert result["locker_released"] is True


# ==============================================================================
# TESTS FOR COMMERCIAL RENT MODULE
# ==============================================================================

def test_rent_unit_calculation_and_penalty():
    """Тест расчета аренды от площади и формулы пени за просрочку."""
    company_id = uuid.uuid4()
    branch_id = uuid.uuid4()

    # Помещение 45.5 м², ставка 800 сом/м²
    unit = Unit(
        id=uuid.uuid4(),
        company_id=company_id,
        branch_id=branch_id,
        number="Б-104",
        floor=1,
        area_sqm=Decimal("45.50"),
        rate_per_sqm=Money(Decimal("800.00")),
    )
    monthly_rent = unit.calculate_monthly_rent()
    assert monthly_rent.amount == Decimal("36400.00")

    # Договор со ставкой пени 0.1% в день
    lease = Lease(
        id=uuid.uuid4(),
        company_id=company_id,
        branch_id=branch_id,
        tenant_id=uuid.uuid4(),
        number="А-2026/031",
        monthly_rent=monthly_rent,
        penalty_pct=Decimal("0.10"),
    )

    # Пример формулы из ТЗ: Пеня = Долг × ставка в день × дней просрочки
    # Долг 36 400 сом, 10 дней просрочки → 36400 * 0.001 * 10 = 364 сом
    penalty = lease.calculate_penalty(debt=monthly_rent, days_overdue=10)
    assert penalty.amount == Decimal("364.00")


def test_rent_fifo_payment_allocation():
    """Тест разнесения оплаты арендатора по методу FIFO (старые долги первыми)."""
    company_id = uuid.uuid4()
    branch_id = uuid.uuid4()
    lease_id = uuid.uuid4()
    tenant_id = uuid.uuid4()

    # Начисление за сентябрь (старое, просроченное): 20 000 сом
    charge_sep = Charge(
        id=uuid.uuid4(),
        company_id=company_id,
        branch_id=branch_id,
        lease_id=lease_id,
        tenant_id=tenant_id,
        type="rent",
        period="2026-09",
        amount=Money(Decimal("20000.00")),
        due_date=date(2026, 9, 5),
        is_paid=False,
    )

    # Начисление за октябрь: 20 000 сом
    charge_oct = Charge(
        id=uuid.uuid4(),
        company_id=company_id,
        branch_id=branch_id,
        lease_id=lease_id,
        tenant_id=tenant_id,
        type="rent",
        period="2026-10",
        amount=Money(Decimal("20000.00")),
        due_date=date(2026, 10, 5),
        is_paid=False,
    )

    # Арендатор вносит частичную оплату 25 000 сом
    allocations, advance = RentBillingUseCase.process_tenant_payment(
        payment_amount=Money(Decimal("25000.00")),
        unpaid_charges=[charge_oct, charge_sep],  # передаем в произвольном порядке
    )

    # 1. Сентябрь должен быть закрыт полностью (20 000)
    assert charge_sep.is_paid is True
    assert charge_sep.paid_amount.amount == Decimal("20000.00")

    # 2. Октябрь закрыт частично (5 000 из 20 000)
    assert charge_oct.is_paid is False
    assert charge_oct.paid_amount.amount == Decimal("5000.00")
    assert charge_oct.remaining_due.amount == Decimal("15000.00")
    assert advance.amount == Decimal("0.00")


def test_kyrgyzstan_payroll_calculations():
    """Тест точного расчета налогов и зарплаты КР по формулам из ТЗ."""
    # Оклад 50 000 сом, премия 10 000 сом → Начислено 60 000 сом
    base_salary = Money(Decimal("50000.00"))
    bonus = Money(Decimal("10000.00"))

    result = PayrollKRCalculator.calculate(base_salary, bonus)

    gross = Decimal("60000.00")
    # Соцфонд работника = 10% от 60 000 = 6 000
    assert result["social_fund_worker"].amount == Decimal("6000.00")

    # ПН = (60 000 - 6 000) * 10% = 5 400
    assert result["income_tax"].amount == Decimal("5400.00")

    # На руки = 60 000 - 6 000 - 5 400 = 48 600
    assert result["net_salary"].amount == Decimal("48600.00")

    # Аванс = 50 000 * 40% = 20 000 (округление до 100 сом)
    assert result["advance"].amount == Decimal("20000.00")

    # К выплате = 48 600 - 20 000 = 28 600
    assert result["payout"].amount == Decimal("28600.00")

    # Взнос работодателя = 60 000 * 17.25% = 10 350
    assert result["employer_contribution"].amount == Decimal("10350.00")

    # Полная стоимость компании = 60 000 + 10 350 = 70 350
    assert result["total_company_cost"].amount == Decimal("70350.00")


def test_reconciliation_act_generation():
    """Тест генератора бухгалтерского Акта сверки."""
    tenant = Tenant(
        id=uuid.uuid4(),
        company_id=uuid.uuid4(),
        name="ОсОО «Бизнес Ритейл»",
        legal_form="ОсОО",
        inn="01234567891011",
    )

    opening_balance = Money(Decimal("5000.00"))  # долг на начало периода 5 000
    debit_items = [
        {"date": date(2026, 10, 1), "doc": "Начисление аренды за октябрь", "amount": Money(Decimal("40000.00"))},
        {"date": date(2026, 10, 15), "doc": "Штраф за курение", "amount": Money(Decimal("2000.00"))},
    ]
    credit_items = [
        {"date": date(2026, 10, 10), "doc": "Оплата через Банк", "amount": Money(Decimal("45000.00"))},
    ]

    act = ReconciliationActBuilder.build_act(
        tenant=tenant,
        period_from=date(2026, 10, 1),
        period_to=date(2026, 10, 31),
        opening_balance=opening_balance,
        debit_items=debit_items,
        credit_items=credit_items,
    )

    # Сальдо на конец: 5 000 + 42 000 (дебет) - 45 000 (кредит) = 2 000 сом долга
    assert act["opening_balance"] == Decimal("5000.00")
    assert act["total_debit"] == Decimal("42000.00")
    assert act["total_credit"] == Decimal("45000.00")
    assert act["closing_balance"] == Decimal("2000.00")
    assert "2000.00 сом" in act["conclusion_phrase"]
    assert len(act["rows"]) == 3
