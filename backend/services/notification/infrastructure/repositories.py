import os
import uuid
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime, timezone
from typing import List, Optional

from backend.services.notification.domain.models import Notification, ScheduledReminder


class NotificationRepository:
    """PostgreSQL persistent repository for notifications and scheduled reminders."""

    def __init__(self, dsn: Optional[str] = None):
        self.dsn = dsn or os.getenv(
            "DATABASE_URL",
            f"postgresql://{os.getenv('DB_USER', 'svc_notify')}:{os.getenv('DB_PASSWORD', 'svc_notify_secret')}@{os.getenv('DB_HOST', 'localhost')}:{os.getenv('DB_PORT', '5432')}/{os.getenv('DB_NAME', 'nurcrm')}"
        )

    def _get_conn(self):
        return psycopg2.connect(self.dsn)

    def save_notification(self, n: Notification) -> None:
        with self._get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO notify.notifications (id, company_id, channel, recipient, title, body, status, sent_at, created_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (id) DO UPDATE SET
                        status = EXCLUDED.status,
                        sent_at = EXCLUDED.sent_at;
                    """,
                    (
                        str(n.id),
                        str(n.company_id),
                        n.channel,
                        n.recipient,
                        n.title,
                        n.body,
                        n.status,
                        n.sent_at,
                        n.created_at,
                    ),
                )
            conn.commit()

    def list_by_company(self, company_id: uuid.UUID) -> List[Notification]:
        with self._get_conn() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    """
                    SELECT id, company_id, channel, recipient, title, body, status, sent_at, created_at
                    FROM notify.notifications
                    WHERE company_id = %s
                    ORDER BY created_at DESC;
                    """,
                    (str(company_id),),
                )
                rows = cur.fetchall()
                return [
                    Notification(
                        id=uuid.UUID(str(r["id"])),
                        company_id=uuid.UUID(str(r["company_id"])),
                        channel=r["channel"],
                        recipient=r["recipient"],
                        title=r["title"],
                        body=r["body"],
                        status=r["status"],
                        sent_at=r["sent_at"],
                        created_at=r["created_at"],
                    )
                    for r in rows
                ]

    def schedule_reminder(self, r: ScheduledReminder) -> None:
        with self._get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO notify.scheduled_reminders (id, company_id, appointment_id, reminder_type, remind_at, is_sent, created_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (id) DO UPDATE SET
                        remind_at = EXCLUDED.remind_at,
                        is_sent = EXCLUDED.is_sent;
                    """,
                    (
                        str(r.id),
                        str(r.company_id),
                        str(r.appointment_id),
                        r.reminder_type,
                        r.remind_at,
                        r.is_sent,
                        r.created_at,
                    ),
                )
            conn.commit()

    def cancel_reminders_for_appointment(self, appointment_id: uuid.UUID) -> None:
        with self._get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    DELETE FROM notify.scheduled_reminders
                    WHERE appointment_id = %s;
                    """,
                    (str(appointment_id),),
                )
            conn.commit()

    def get_pending_reminders(self, current_time: datetime) -> List[ScheduledReminder]:
        with self._get_conn() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    """
                    SELECT id, company_id, appointment_id, reminder_type, remind_at, is_sent, created_at
                    FROM notify.scheduled_reminders
                    WHERE is_sent = false AND remind_at <= %s
                    ORDER BY remind_at ASC;
                    """,
                    (current_time,),
                )
                rows = cur.fetchall()
                return [
                    ScheduledReminder(
                        id=uuid.UUID(str(r["id"])),
                        company_id=uuid.UUID(str(r["company_id"])),
                        appointment_id=uuid.UUID(str(r["appointment_id"])),
                        reminder_type=r["reminder_type"],
                        remind_at=r["remind_at"],
                        is_sent=r["is_sent"],
                        created_at=r["created_at"],
                    )
                    for r in rows
                ]

    def mark_reminder_sent(self, reminder_id: uuid.UUID) -> None:
        with self._get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE notify.scheduled_reminders
                    SET is_sent = true
                    WHERE id = %s;
                    """,
                    (str(reminder_id),),
                )
            conn.commit()
