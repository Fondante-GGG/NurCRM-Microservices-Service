from typing import List, Optional
import uuid
from datetime import datetime, timezone

from backend.services.notification.domain.models import Notification, ScheduledReminder


class NotificationRepository:
    def __init__(self):
        self.notifications: List[Notification] = []
        self.reminders: List[ScheduledReminder] = []

    def save_notification(self, n: Notification) -> None:
        self.notifications.append(n)

    def list_by_company(self, company_id: uuid.UUID) -> List[Notification]:
        return [n for n in self.notifications if n.company_id == company_id]

    def schedule_reminder(self, r: ScheduledReminder) -> None:
        self.reminders.append(r)

    def cancel_reminders_for_appointment(self, appointment_id: uuid.UUID) -> None:
        self.reminders = [r for r in self.reminders if r.appointment_id != appointment_id]

    def get_pending_reminders(self, current_time: datetime) -> List[ScheduledReminder]:
        return [r for r in self.reminders if not r.is_sent and r.remind_at <= current_time]

    def mark_reminder_sent(self, reminder_id: uuid.UUID) -> None:
        for r in self.reminders:
            if r.id == reminder_id:
                r.is_sent = True
                break
