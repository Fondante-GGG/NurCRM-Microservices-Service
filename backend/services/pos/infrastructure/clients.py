import os
import uuid
from decimal import Decimal
from typing import List

from libs.common.exceptions import ValidationError
from libs.common.http_client import InternalServiceClient
from backend.services.pos.domain.models import CatalogProduct


class HttpCatalogClient:
    def __init__(self):
        self.client = InternalServiceClient(
            base_url=os.getenv("CATALOG_SERVICE_URL", "http://localhost:8002"),
            sender_service="pos-service",
            target_service="catalog-service",
        )

    def get_products(self, company_id: uuid.UUID, product_ids: List[uuid.UUID]) -> List[CatalogProduct]:
        response = self.client.get(
            "/internal/v1/products/",
            params={
                "company_id": str(company_id),
                "product_ids": ",".join(str(product_id) for product_id in product_ids),
            },
        )
        if not isinstance(response, list):
            raise ValidationError("Catalog returned an invalid product list")
        try:
            return [
                CatalogProduct(
                    id=uuid.UUID(item["id"]),
                    name=str(item["name"]),
                    sku=str(item.get("sku", "")),
                    price=Decimal(str(item["price"])),
                    unit_code=str(item["unit_code"]),
                    minimum_quantity=Decimal(str(item["minimum_quantity"])),
                    quantity_step=Decimal(str(item["quantity_step"])),
                    is_active=bool(item["is_active"]),
                )
                for item in response
            ]
        except (KeyError, TypeError, ValueError):
            raise ValidationError("Catalog returned an invalid product record")


class HttpInventoryClient:
    def __init__(self):
        self.client = InternalServiceClient(
            base_url=os.getenv("INVENTORY_SERVICE_URL", "http://localhost:8009"),
            sender_service="pos-service",
            target_service="inventory-service",
        )

    def reserve(self, company_id: uuid.UUID, idempotency_key: str, items: list) -> uuid.UUID:
        response = self.client.post(
            "/internal/v1/reservations/",
            json_data={
                "company_id": str(company_id),
                "idempotency_key": idempotency_key,
                "items": items,
            },
            idempotency_key=idempotency_key,
        )
        try:
            return uuid.UUID(response["id"])
        except (KeyError, TypeError, ValueError):
            raise ValidationError("Inventory returned an invalid reservation")

    def commit(self, company_id: uuid.UUID, reservation_id: uuid.UUID) -> None:
        self.client.post(
            f"/internal/v1/reservations/{reservation_id}/commit/",
            json_data={"company_id": str(company_id)},
            idempotency_key=f"commit:{reservation_id}",
        )
