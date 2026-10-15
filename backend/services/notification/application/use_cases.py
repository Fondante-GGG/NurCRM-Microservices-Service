import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional, List

from backend.services.notification.domain.models import Notification, ScheduledReminder
from backend.services.notification.infrastructure.repositories import NotificationRepository


class SendNotificationUseCase:
    def __init__(self, repo: NotificationRepository):
        self.repo = repo

    def execute(self, company_id: uuid.UUID, channel: str, recipient: str, body: str, title: Optional[str] = None) -> Notification:
        notif = Notification(
            id=uuid.uuid4(),
            company_id=company_id,
            channel=channel,
            recipient=recipient,
            body=body,
            title=title,
            status="sent",
        )
        self.repo.save_notification(notif)
        return notif


class ScheduleAppointmentRemindersUseCase:
    def __init__(self, repo: NotificationRepository):
        self.repo = repo

    def execute(self, company_id: uuid.UUID, appointment_id: uuid.UUID, start_at: datetime) -> None:
        now = datetime.now(timezone.utc)
        remind_24h = start_at - timedelta(hours=24)
        if remind_24h > now:
            self.repo.schedule_reminder(ScheduledReminder(
                id=uuid.uuid4(),
                company_id=company_id,
                appointment_id=appointment_id,
                reminder_type="24h",
                remind_at=remind_24h,
            ))

        remind_2h = start_at - timedelta(hours=2)
        if remind_2h > now:
            self.repo.schedule_reminder(ScheduledReminder(
                id=uuid.uuid4(),
                company_id=company_id,
                appointment_id=appointment_id,
                reminder_type="2h",
                remind_at=remind_2h,
            ))


class ProcessPendingRemindersUseCase:
    def __init__(self, repo: NotificationRepository):
        self.repo = repo

    def execute(self) -> int:
        now = datetime.now(timezone.utc)
        pending = self.repo.get_pending_reminders(now)
        for r in pending:
            # Simulate sending WhatsApp/SMS reminder
            self.repo.save_notification(Notification(
                id=uuid.uuid4(),
                company_id=r.company_id,
                channel="whatsapp",
                recipient="клиент",
                body=f"Напоминание о записи #{str(r.appointment_id)[:8]} (за {r.reminder_type})",
                title="Напоминание NurCRM",
            ))
            self.repo.mark_reminder_sent(r.id)
        return len(pending)
