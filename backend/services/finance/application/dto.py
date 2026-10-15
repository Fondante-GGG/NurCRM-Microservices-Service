from dataclasses import dataclass
from typing import Optional
from decimal import Decimal
from datetime import date
import uuid


@dataclass
class AccrualDTO:
    id: str
    company_id: str
    appointment_id: str
    master_id: str
    service_id: Optional[str]
    amount: Decimal
    percent: Decimal
    created_at: str


@dataclass
class SalaryPayoutDTO:
    id: str
    company_id: str
    master_id: str
    amount: Decimal
    date: str
    cashbox: str
    comment: Optional[str]
    created_at: str


@dataclass
class SalarySummaryDTO:
    accrued_total: Decimal
    paid_total: Decimal
    balance: Decimal


@dataclass
class CashShiftDTO:
    id: str
    company_id: str
    user_id: str
    cashbox: str
    opening_cash: Decimal
    closing_cash: Optional[Decimal]
    sales_total: Decimal
    sales_count: int
    status: str
    opened_at: str
    closed_at: Optional[str]
