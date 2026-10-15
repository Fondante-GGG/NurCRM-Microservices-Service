from __future__ import annotations
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
import uuid
import json
from typing import Any, Dict, Optional


class EventTypes:
    AUTH_COMPANY_CHANGED = "auth.company.changed"
    AUTH_EMPLOYEE_CHANGED = "auth.employee.changed"

    CATALOG_SERVICE_CHANGED = "catalog.service.changed"

    CLIENT_CLIENT_CREATED = "client.client.created"
    CLIENT_CLIENT_UPDATED = "client.client.updated"

    SCHEDULE_APPOINTMENT_CREATED = "schedule.appointment.created"
    SCHEDULE_APPOINTMENT_UPDATED = "schedule.appointment.updated"
    SCHEDULE_APPOINTMENT_CANCELED = "schedule.appointment.canceled"
    SCHEDULE_APPOINTMENT_COMPLETED = "schedule.appointment.completed"

    BOOKING_REQUEST_CREATED = "booking.request.created"
    BOOKING_REQUEST_CONFIRMED = "booking.request.confirmed"

    FINANCE_PAYOUT_CREATED = "finance.payout.created"
    FINANCE_SHIFT_CLOSED = "finance.shift.closed"


@dataclass
class EventEnvelope:
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    type: str = ""
    version: int = 1
    occurred_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    company_id: str = ""
    trace_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    actor_id: Optional[str] = None
    sid: Optional[str] = None
    data: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), default=str, ensure_ascii=False)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> EventEnvelope:
        return cls(
            event_id=str(data.get("event_id", uuid.uuid4())),
            type=data.get("type", ""),
            version=int(data.get("version", 1)),
            occurred_at=str(data.get("occurred_at", datetime.now(timezone.utc).isoformat())),
            company_id=str(data.get("company_id", "")),
            trace_id=str(data.get("trace_id", uuid.uuid4())),
            actor_id=data.get("actor_id"),
            sid=data.get("sid"),
            data=data.get("data", {}),
        )

    @classmethod
    def from_json(cls, json_str: str) -> EventEnvelope:
        return cls.from_dict(json.loads(json_str))
