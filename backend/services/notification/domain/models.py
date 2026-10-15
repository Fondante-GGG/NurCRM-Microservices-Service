from dataclasses import dataclass, field
import uuid
from datetime import datetime, timezone
from typing import Optional


@dataclass
class Notification:
    id: uuid.UUID
    company_id: uuid.UUID
    channel: str  # sms, whatsapp
    recipient: str
    body: str
    title: Optional[str] = None
    status: str = "sent"  # pending, sent, failed
    sent_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class ScheduledReminder:
    id: uuid.UUID
    company_id: uuid.UUID
    appointment_id: uuid.UUID
    reminder_type: str  # 24h, 2h
    remind_at: datetime
    is_sent: bool = False
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
