from dataclasses import dataclass
from typing import Optional, List
import uuid


@dataclass
class LoginRequestDTO:
    email: str
    password: str
    device: Optional[str] = None
    ip_address: Optional[str] = None


@dataclass
class LoginResponseDTO:
    access_token: str
    refresh_token: str
    user_id: str
    company_id: str
    role: str
    permissions: List[str]
    first_name: str
    last_name: str
    email: str
    company_slug: str


@dataclass
class RefreshRequestDTO:
    refresh_token: str


@dataclass
class CreateEmployeeDTO:
    company_id: uuid.UUID
    first_name: str
    last_name: str
    email: str
    password: str
    phone_number: str
    role: str = "master"
    role_display: str = "Специалист"
    avatar: Optional[str] = None
    branch_ids: Optional[List[uuid.UUID]] = None
