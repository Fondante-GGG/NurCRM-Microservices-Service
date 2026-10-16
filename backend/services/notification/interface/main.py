from fastapi import FastAPI, Depends, Header, HTTPException
from pydantic import BaseModel
from typing import Optional, List
import uuid

from libs.common.auth import verify_token, verify_internal_token, JWTUser
from backend.services.notification.infrastructure.repositories import NotificationRepository
from backend.services.notification.application.use_cases import (
    SendNotificationUseCase,
    ProcessPendingRemindersUseCase,
    ScheduleAppointmentRemindersUseCase,
)

app = FastAPI(title="NurCRM Notification Service", version="1.0.0")
repo = NotificationRepository()


def get_current_user(authorization: Optional[str] = Header(None)) -> JWTUser:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail={"code": "unauthorized", "message": "Missing token"})
    token = authorization.split(" ")[1]
    try:
        return verify_token(token)
    except Exception as e:
        raise HTTPException(status_code=401, detail={"code": "unauthorized", "message": str(e)})


def verify_internal_auth(authorization: Optional[str] = Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail={"code": "unauthorized", "message": "Missing internal service Bearer token"})
    token = authorization.split(" ")[1]
    try:
        return verify_internal_token(token, expected_audience="notification-service")
    except Exception as e:
        raise HTTPException(status_code=401, detail={"code": "unauthorized", "message": str(e)})


class SendNotificationRequest(BaseModel):
    channel: str = "whatsapp"
    recipient: str
    body: str
    title: Optional[str] = None


@app.post("/api/v1/notifications/send/")
def send_notification(req: SendNotificationRequest, current_user: JWTUser = Depends(get_current_user)):
    use_case = SendNotificationUseCase(repo)
    notif = use_case.execute(
        company_id=uuid.UUID(current_user.company_id),
        channel=req.channel,
        recipient=req.recipient,
        body=req.body,
        title=req.title,
    )
    return {
        "id": str(notif.id),
        "channel": notif.channel,
        "recipient": notif.recipient,
        "status": notif.status,
        "sent_at": notif.sent_at.isoformat(),
    }


@app.get("/api/v1/notifications/")
def list_notifications(current_user: JWTUser = Depends(get_current_user)):
    items = repo.list_by_company(uuid.UUID(current_user.company_id))
    return [
        {
            "id": str(n.id),
            "channel": n.channel,
            "recipient": n.recipient,
            "title": n.title,
            "body": n.body,
            "status": n.status,
            "sent_at": n.sent_at.isoformat(),
        }
        for n in items
    ]


@app.post("/internal/v1/notifications/process-reminders/")
def trigger_reminders(auth = Depends(verify_internal_auth)):
    use_case = ProcessPendingRemindersUseCase(repo)
    count = use_case.execute()
    return {"reminders_sent": count}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8007)
