from dataclasses import dataclass
from typing import List, Dict, Any, Optional
from decimal import Decimal


@dataclass
class MasterRankingItem:
    master_id: str
    master_name: str
    appointments_count: int
    revenue: Decimal


@dataclass
class ServiceRankingItem:
    service_id: str
    service_name: str
    orders_count: int
    revenue: Decimal


@dataclass
class ClientRankingItem:
    client_id: str
    client_name: str
    visits_count: int
    total_spent: Decimal


@dataclass
class AnalyticsDashboard:
    period: str
    revenue_total: Decimal
    cash_in: Decimal
    cash_out: Decimal
    avg_ticket: Decimal
    total_appointments: int
    completed_count: int
    canceled_count: int
    no_show_count: int
    conversion_rate: float
    top_masters: List[MasterRankingItem]
    top_services: List[ServiceRankingItem]
    top_clients: List[ClientRankingItem]
    weekday_distribution: Dict[str, int]
    daily_cashflow: List[Dict[str, Any]]
