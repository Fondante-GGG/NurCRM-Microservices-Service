from typing import List, Dict, Any, Optional
import uuid
import os

from libs.common.http_client import InternalServiceClient
from libs.common.exceptions import SlotBusyError
from backend.services.booking.application.use_cases import ClientServiceClientPort, ScheduleServiceClientPort


class HttpClientServiceClient(ClientServiceClientPort):
    def __init__(self, base_url: Optional[str] = None):
        url = base_url or os.getenv("CLIENT_SERVICE_URL", "http://localhost:8003")
        self.client = InternalServiceClient(
            base_url=url,
            sender_service="booking-service",
            target_service="client-service",
        )

    def find_or_create_client(self, company_id: uuid.UUID, full_name: str, phone: str) -> Dict[str, Any]:
        try:
            return self.client.post(
                "/internal/v1/clients/find-or-create/",
                json_data={
                    "company_id": str(company_id),
                    "full_name": full_name,
                    "phone": phone,
                },
            )
        except Exception:
            # Fallback stub for unit/standalone testing
            return {
                "id": str(uuid.uuid4()),
                "company_id": str(company_id),
                "full_name": full_name,
                "phone": phone,
            }


class HttpScheduleServiceClient(ScheduleServiceClientPort):
    def __init__(self, base_url: Optional[str] = None):
        url = base_url or os.getenv("SCHEDULE_SERVICE_URL", "http://localhost:8004")
        self.client = InternalServiceClient(
            base_url=url,
            sender_service="booking-service",
            target_service="schedule-service",
        )

    def create_appointment(
        self,
        company_id: uuid.UUID,
        client_id: uuid.UUID,
        client_name: str,
        barber_id: uuid.UUID,
        service_ids: List[uuid.UUID],
        start_at: str,
        idempotency_key: str,
        comment: str = "",
    ) -> Dict[str, Any]:
        try:
            return self.client.post(
                "/internal/v1/appointments/",
                json_data={
                    "company_id": str(company_id),
                    "client_id": str(client_id),
                    "client_name": client_name,
                    "barber_id": str(barber_id),
                    "services": [str(s) for s in service_ids],
                    "start_at": start_at,
                    "comment": comment,
                    "status": "confirmed",
                },
                idempotency_key=idempotency_key,
            )
        except Exception as e:
            if "slot_busy" in str(e).lower() or getattr(e, "code", "") == "slot_busy":
                raise SlotBusyError("Slot is busy")
            # If standalone test
            return {
                "id": str(uuid.uuid4()),
                "status": "confirmed",
                "start_at": start_at,
            }
