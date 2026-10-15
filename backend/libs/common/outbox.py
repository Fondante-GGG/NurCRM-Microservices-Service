from __future__ import annotations
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any, Protocol
import json

from libs.common.events import EventEnvelope


@dataclass
class OutboxRecord:
    id: uuid.UUID = field(default_factory=uuid.uuid4)
    event_id: uuid.UUID = field(default_factory=uuid.uuid4)
    event_type: str = ""
    payload: Dict[str, Any] = field(default_factory=dict)
    status: str = "pending"  # pending, published, failed
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    published_at: Optional[datetime] = None
    retry_count: int = 0
    error: Optional[str] = None


class OutboxRepository(Protocol):
    def save(self, record: OutboxRecord) -> None:
        ...

    def get_pending(self, limit: int = 50) -> List[OutboxRecord]:
        ...

    def mark_published(self, record_id: uuid.UUID) -> None:
        ...

    def mark_failed(self, record_id: uuid.UUID, error: str) -> None:
        ...


class InboxRepository(Protocol):
    def is_processed(self, event_id: uuid.UUID) -> bool:
        ...

    def mark_processed(self, event_id: uuid.UUID, event_type: str) -> None:
        ...


class InMemoryOutboxRepository:
    def __init__(self):
        self.records: Dict[uuid.UUID, OutboxRecord] = {}

    def save(self, record: OutboxRecord) -> None:
        self.records[record.id] = record

    def get_pending(self, limit: int = 50) -> List[OutboxRecord]:
        pending = [r for r in self.records.values() if r.status == "pending"]
        return pending[:limit]

    def mark_published(self, record_id: uuid.UUID) -> None:
        if record_id in self.records:
            self.records[record_id].status = "published"
            self.records[record_id].published_at = datetime.now(timezone.utc)

    def mark_failed(self, record_id: uuid.UUID, error: str) -> None:
        if record_id in self.records:
            self.records[record_id].status = "failed"
            self.records[record_id].retry_count += 1
            self.records[record_id].error = error


class InMemoryInboxRepository:
    def __init__(self):
        self.processed: set[uuid.UUID] = set()

    def is_processed(self, event_id: uuid.UUID) -> bool:
        return event_id in self.processed

    def mark_processed(self, event_id: uuid.UUID, event_type: str) -> None:
        self.processed.add(event_id)
