from typing import List, Optional
import uuid
import os
from decimal import Decimal

from libs.common.domain import Money
from libs.common.http_client import InternalServiceClient
from backend.services.schedule.domain.models import ServiceSnapshot
from backend.services.schedule.application.use_cases import CatalogClientPort


class HttpCatalogClient(CatalogClientPort):
    def __init__(self, base_url: Optional[str] = None):
        url = base_url or os.getenv("CATALOG_SERVICE_URL", "http://localhost:8002")
        self.client = InternalServiceClient(
            base_url=url,
            sender_service="schedule-service",
            target_service="catalog-service",
        )

    def get_services(self, company_id: uuid.UUID, service_ids: List[uuid.UUID]) -> List[ServiceSnapshot]:
        ids_str = ",".join(str(s) for s in service_ids)
        res = self.client.get(
            "/internal/v1/services/",
            params={"company_id": str(company_id), "service_ids": ids_str},
        )
        return [
            ServiceSnapshot(
                service_id=uuid.UUID(item["id"]),
                name=item["name"],
                price=Money(Decimal(str(item["price"]))),
                time_minutes=int(item["time_minutes"]),
            )
            for item in res
        ]
