from dataclasses import dataclass
from typing import Optional, List, Dict, Any
from decimal import Decimal
from datetime import date, time
import uuid


@dataclass
class CreateBookingRequestDTO:
    company_id: uuid.UUID
    client_name: str
    client_phone: str
    services: List[Dict[str, Any]]
    date: date
    time_start: time
    time_end: time
    total_price: Decimal
    total_duration_min: int
    master_id: Optional[uuid.UUID] = None
    payment_method: str = "cash"
    client_comment: str = ""


@dataclass
class BookingRequestDTO:
    id: str
    company_id: str
    client_name: str
    client_phone: str
    services: List[Dict[str, Any]]
    master_id: Optional[str]
    date: str
    time_start: str
    time_end: str
    total_price: Decimal
    total_duration_min: int
    payment_method: str
    client_comment: str
    status: str
    appointment_id: Optional[str]
    version: int
    created_at: str
