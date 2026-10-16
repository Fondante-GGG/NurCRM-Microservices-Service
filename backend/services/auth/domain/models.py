from __future__ import annotations
from dataclasses import dataclass, field
import uuid
from datetime import datetime, time, timezone
from typing import List, Optional
import hashlib
import hmac
import secrets

from libs.common.domain import AggregateRoot, Entity
from libs.common.auth import Permissions


@dataclass
class Role:
    OWNER = "owner"
    ADMIN = "admin"
    MASTER = "master"
    SUPPORT = "support"

    CHOICES = [OWNER, ADMIN, MASTER, SUPPORT]

    @classmethod
    def default_permissions(cls, role: str) -> List[str]:
        if role in (cls.OWNER, cls.SUPPORT):
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
    industry: Optional[str] = None  # barber | beauty | procedure | massage
    intake: str = "schedule"        # schedule | flow
    sector: str = "Услуги"
    legal_name: str = ""
    inn: str = ""
    okpo: str = ""
    account: str = ""
    bik: str = ""
    address: str = ""
    phones: List[str] = field(default_factory=list)
    blocked: bool = False
    plan: str = "free"             # free | trial | paid
    temp_access_until: Optional[datetime] = None
    appointment_work_start: time = field(default_factory=lambda: time(9, 0))
    appointment_work_end: time = field(default_factory=lambda: time(21, 0))
    subscription_plan: str = "Стандарт"
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class Branch(Entity):
    name: str = ""
    address: str = ""
    is_active: bool = True
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class SupportTicket(AggregateRoot):
    topic: str = ""          # industry | setup | bug | other
    message: str = ""
    contact: str = ""
    share_access: bool = False
    status: str = "new"      # new | in_progress | done
    assignee: str = ""
    reply: str = ""
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class SupportLog(Entity):
    at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    agent: str = ""
    action: str = ""


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
    def hash_password(password: str, salt: Optional[str] = None) -> str:
        iterations = 100000
        if salt is None:
            salt = secrets.token_hex(16)
        computed_hash = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), iterations).hex()
        return f"pbkdf2_sha256${iterations}${salt}${computed_hash}"

    def check_password(self, password: str) -> bool:
        if not self.password_hash:
            return False
        # Modern salted pbkdf2 format: pbkdf2_sha256$<iterations>$<salt>$<hash>
        if self.password_hash.startswith("pbkdf2_sha256$"):
            try:
                parts = self.password_hash.split("$")
                if len(parts) == 4:
                    iterations = int(parts[1])
                    salt = parts[2]
                    expected_hash = parts[3]
                    actual_hash = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), iterations).hex()
                    return hmac.compare_digest(expected_hash, actual_hash)
            except Exception:
                return False
        # Legacy fallback format: static salt
        legacy_salt = "nurcrm_secure_salt_"
        legacy_hash = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), legacy_salt.encode("utf-8"), 100000).hex()
        return hmac.compare_digest(self.password_hash, legacy_hash)

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
