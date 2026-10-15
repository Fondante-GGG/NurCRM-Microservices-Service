from dataclasses import dataclass
from typing import Optional
from datetime import date
import uuid


@dataclass
class ClientDTO:
    id: str
    company_id: str
    full_name: str
    phone: str
    birth_date: Optional[str]
    status: str
    notes: Optional[str]
    version: int


@dataclass
class CreateClientDTO:
    company_id: uuid.UUID
    full_name: str
    phone: str
    birth_date: Optional[date] = None
    status: str = "active"
    notes: Optional[str] = None


@dataclass
class UpdateClientDTO:
    full_name: Optional[str] = None
    phone: Optional[str] = None
    birth_date: Optional[date] = None
    status: Optional[str] = None
    notes: Optional[str] = None
    expected_version: Optional[int] = None


@dataclass
class ClientDocumentDTO:
    id: str
    company_id: str
    client_id: str
    file_name: str
    file_size: int
    file_comment: Optional[str]
    created_at: str
