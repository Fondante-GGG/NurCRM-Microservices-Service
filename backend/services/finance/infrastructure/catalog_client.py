from typing import Optional
import uuid
import os
from decimal import Decimal

from libs.common.http_client import InternalServiceClient
from backend.services.finance.application.use_cases import CatalogClientPort


class HttpCatalogClient(CatalogClientPort):
    def __init__(self, base_url: Optional[str] = None):
        url = base_url or os.getenv("CATALOG_SERVICE_URL", "http://localhost:8002")
        self.client = InternalServiceClient(
            base_url=url,
            sender_service="finance-service",
            target_service="catalog-service",
        )

    def get_rate(self, company_id: uuid.UUID, service_id: uuid.UUID, master_id: Optional[uuid.UUID] = None) -> Decimal:
        try:
            params = {"company_id": str(company_id)}
            if master_id:
                params["master_id"] = str(master_id)
            res = self.client.get(f"/internal/v1/rates/{service_id}/", params=params)
            percent_val = res.get("percent")
            if percent_val is not None:
                return Decimal(str(percent_val))
            return Decimal("0.00")
        except Exception:
            return Decimal("0.00")
