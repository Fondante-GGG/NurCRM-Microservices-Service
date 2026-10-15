from dataclasses import dataclass
from typing import Optional, List
from decimal import Decimal
import uuid


@dataclass
class ServiceCategoryDTO:
    id: str
    company_id: str
    name: str
    is_active: bool
    version: int


@dataclass
class ServiceDTO:
    id: str
    company_id: str
    category_id: str
    name: str
    price: Decimal
    time_minutes: int
    barbers: List[str]
    is_active: bool
    version: int


@dataclass
class CreateServiceDTO:
    company_id: uuid.UUID
    category_id: uuid.UUID
    name: str
    price: Decimal
    time_minutes: int
    barbers: List[uuid.UUID]
    is_active: bool = True


@dataclass
class UpdateServiceDTO:
    name: Optional[str] = None
    category_id: Optional[uuid.UUID] = None
    price: Optional[Decimal] = None
    time_minutes: Optional[int] = None
    barbers: Optional[List[uuid.UUID]] = None
    is_active: Optional[bool] = None
    expected_version: Optional[int] = None


@dataclass
class SalaryRateDTO:
    id: str
    company_id: str
    service_id: str
    master_id: Optional[str]
    percent: Decimal
