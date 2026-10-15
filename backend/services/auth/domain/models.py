from __future__ import annotations
from dataclasses import dataclass, field
import uuid
from datetime import datetime, time, timezone
from typing import List, Optional
import hashlib
import hmac

from libs.common.domain import AggregateRoot, Entity
from libs.common.auth import Permissions


@dataclass
class Role:
    OWNER = "owner"
    ADMIN = "admin"
    MASTER = "master"

    CHOICES = [OWNER, ADMIN, MASTER]

    @classmethod
    def default_permissions(cls, role: str) -> List[str]:
        if role == cls.OWNER:
            return Permissions.ALL
        elif role == cls.ADMIN:
            return [
                Permissions.CAN_VIEW_BARBER_RECORDS,
                Permissions.CAN_VIEW_BARBER_CLIENTS,
                Permissions.CAN_VIEW_BARBER_SERVICES,
                Permissions.CAN_VIEW_BARBER_HISTORY,
                Permissions.CAN_VIEW_CASHBOX,
            ]
        elif role == cls.MASTER:
            return [
                Permissions.CAN_VIEW_BARBER_RECORDS,
                Permissions.CAN_VIEW_BARBER_SERVICES,
            ]
        return []


@dataclass
class Company(AggregateRoot):
    name: str = ""
    slug: str = ""
    industry: str = "Услуги"
    sector: str = "Услуги"
    appointment_work_start: time = field(default_factory=lambda: time(9, 0))
    appointment_work_end: time = field(default_factory=lambda: time(21, 0))
    subscription_plan: str = "Стандарт"
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class Employee(AggregateRoot):
    first_name: str = ""
    last_name: str = ""
    email: str = ""
    password_hash: str = ""
    phone_number: str = ""
    role: str = Role.MASTER
    role_display: str = "Специалист"
    avatar: Optional[str] = None
    branch_ids: List[uuid.UUID] = field(default_factory=list)
    is_active: bool = True
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @staticmethod
    def hash_password(password: str) -> str:
        salt = "nurcrm_secure_salt_"
        return hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 100000).hex()

    def check_password(self, password: str) -> bool:
        return hmac.compare_digest(self.password_hash, self.hash_password(password))

    @property
    def permissions(self) -> List[str]:
        return Role.default_permissions(self.role)


@dataclass
class Session(Entity):
    company_id: uuid.UUID
    user_id: uuid.UUID
    refresh_token_hash: str
    device: Optional[str] = None
    ip_address: Optional[str] = None
    is_revoked: bool = False
    last_seen: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
