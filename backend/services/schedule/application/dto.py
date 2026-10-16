from dataclasses import dataclass
from typing import Optional, List, Dict, Any
from decimal import Decimal
from datetime import datetime
import uuid


@dataclass
class ServiceItemInputDTO:
    service_id: uuid.UUID
    name: str
    price: Decimal
    time_minutes: int


@dataclass
class CreateAppointmentDTO:
    company_id: uuid.UUID
    client_name: str
    barber_id: Optional[uuid.UUID] = None
    start_at: Optional[datetime] = None
    service_ids: Optional[List[uuid.UUID]] = None
    client_id: Optional[uuid.UUID] = None
    discount: Optional[Decimal] = None
    comment: str = ""
    status: str = "booked"


@dataclass
class UpdateAppointmentDTO:
    start_at: Optional[datetime] = None
    barber_id: Optional[uuid.UUID] = None
    service_ids: Optional[List[uuid.UUID]] = None
    client_name: Optional[str] = None
    discount: Optional[Decimal] = None
    comment: Optional[str] = None
    status: Optional[str] = None
    expected_version: Optional[int] = None


@dataclass
class AppointmentDTO:
    id: str
    company_id: str
    client_id: Optional[str]
    client_name: str
    barber_id: Optional[str]
    services: List[Dict[str, Any]]
    start_at: str
    end_at: str
    price: Decimal
    discount: Decimal
    status: str
    comment: str
    version: int


@dataclass
class BusySlotDTO:
    start_at: str
    end_at: str
