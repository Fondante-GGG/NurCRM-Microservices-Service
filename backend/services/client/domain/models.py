from __future__ import annotations
from dataclasses import dataclass, field
import uuid
from datetime import date, datetime, timezone
from typing import Optional

from libs.common.domain import AggregateRoot, Entity, Phone
from libs.common.exceptions import ValidationError


@dataclass
class ClientStatus:
    ACTIVE = "active"
    BLACKLIST = "blacklist"

    CHOICES = [ACTIVE, BLACKLIST]


@dataclass
class Client(AggregateRoot):
    full_name: str = ""
    phone: Phone = field(default_factory=lambda: Phone("+996555000000"))
    birth_date: Optional[date] = None
    status: str = ClientStatus.ACTIVE
    notes: Optional[str] = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self):
        if not self.full_name.strip():
            raise ValidationError("Client full name cannot be empty")
        if self.status not in ClientStatus.CHOICES:
            raise ValidationError(f"Invalid client status: {self.status}")

    def blacklist(self, reason: Optional[str] = None) -> None:
        self.status = ClientStatus.BLACKLIST
        if reason:
            self.notes = f"{self.notes or ''}\nBlacklisted reason: {reason}".strip()
        self.increment_version()

    def unblacklist(self) -> None:
        self.status = ClientStatus.ACTIVE
        self.increment_version()


@dataclass
class ClientDocument(Entity):
    company_id: uuid.UUID
    client_id: uuid.UUID
    file_path: str
    file_name: str
    file_size: int
    file_comment: Optional[str] = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self):
        max_size = 10 * 1024 * 1024  # 10 MB
        if self.file_size > max_size:
            raise ValidationError("File size exceeds maximum limit of 10 MB")
