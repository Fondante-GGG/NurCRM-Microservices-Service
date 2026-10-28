from decimal import Decimal, InvalidOperation
import hashlib
import json
import uuid
from typing import Dict, List, Protocol, Tuple

from libs.common.domain import Money
from libs.common.exceptions import ConflictError, CRMException, NotFoundError, ValidationError
from backend.services.pos.domain.models import CatalogProduct, Sale, SaleLine


class CatalogClient(Protocol):
    def get_products(self, company_id: uuid.UUID, product_ids: List[uuid.UUID]) -> List[CatalogProduct]:
        ...


class InventoryClient(Protocol):
    def reserve(self, company_id: uuid.UUID, idempotency_key: str, items: List[Dict]) -> uuid.UUID:
        ...

    def commit(self, company_id: uuid.UUID, reservation_id: uuid.UUID) -> None:
        ...


class SaleRepository(Protocol):
    def get_by_idempotency_key(
        self,
        company_id: uuid.UUID,
        idempotency_key: str,
        request_hash: str,
    ) -> Sale | None:
        ...

    def create_or_get(self, sale: Sale) -> Tuple[Sale, bool]:
        ...

    def set_reservation(self, sale_id: uuid.UUID, reservation_id: uuid.UUID) -> None:
        ...

    def set_status(self, sale_id: uuid.UUID, status: str) -> None:
        ...


def _decimal(value, field_name: str) -> Decimal:
    try:
        result = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        raise ValidationError(f"{field_name} must be a decimal number")
    if not result.is_finite():
        raise ValidationError(f"{field_name} must be finite")
    return result


def _request_hash(payload: Dict) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class CheckoutUseCase:
    def __init__(
        self,
        repository: SaleRepository,
        catalog: CatalogClient,
        inventory: InventoryClient,
    ):
        self.repository = repository
        self.catalog = catalog
        self.inventory = inventory

    def execute(
        self,
        company_id: uuid.UUID,
        cashier_id: uuid.UUID,
        idempotency_key: str,
        payload: Dict,
    ) -> Tuple[Sale, bool]:
        if not idempotency_key or len(idempotency_key) > 128:
            raise ValidationError("Idempotency-Key is required and must be at most 128 characters")
        if not isinstance(payload, dict):
            raise ValidationError("A checkout object is required")
        request_hash = _request_hash(payload)
        existing = self.repository.get_by_idempotency_key(company_id, idempotency_key, request_hash)
        if existing:
            if existing.request_hash != request_hash:
                raise ConflictError("Idempotency key was already used with a different checkout payload")
            if existing.status == "completed":
                return existing, False
            if existing.status == "rejected":
                raise ConflictError("Checkout was rejected", code="checkout_rejected")

        items = payload.get("items")
        if not isinstance(items, list) or not items or len(items) > 200:
            raise ValidationError("items must contain between 1 and 200 lines")

        product_ids = []
        parsed_lines = []
        for item in items:
            if not isinstance(item, dict):
                raise ValidationError("Each checkout line must be an object")
            try:
                product_id = uuid.UUID(str(item["product_id"]))
                quantity = _decimal(item.get("quantity"), "quantity")
                variant_id = uuid.UUID(str(item["variant_id"])) if item.get("variant_id") else None
                branch_id = uuid.UUID(str(item["branch_id"])) if item.get("branch_id") else None
            except (KeyError, ValueError, TypeError):
                raise ValidationError("Each line requires valid product_id and quantity values")
            unit_code = str(item.get("unit_code", "pcs")).strip()
            location_code = str(item.get("location_code", "default")).strip()
            if not unit_code:
                raise ValidationError("unit_code is required")
            if not location_code or len(location_code) > 64:
                raise ValidationError("location_code must contain 1 to 64 characters")
            line_discount = _decimal(item.get("discount", "0"), "discount")
            product_ids.append(product_id)
            parsed_lines.append((item, product_id, variant_id, branch_id, quantity, unit_code, location_code, line_discount))

        if len({line[3] for line in parsed_lines}) > 1:
            raise ValidationError("All items in a sale must belong to the same branch")

        products = {product.id: product for product in self.catalog.get_products(company_id, list(set(product_ids)))}
        if len(products) != len(set(product_ids)):
            raise NotFoundError("One or more products are unavailable")

        sale_lines = []
        for item, product_id, variant_id, branch_id, quantity, unit_code, location_code, line_discount in parsed_lines:
            product = products[product_id]
            product.validate_quantity(quantity, unit_code)
            unit_price = _decimal(product.price, "catalog price")
            if line_discount < 0 or line_discount > unit_price * quantity:
                raise ValidationError("Line discount is outside the line total")
            sale_lines.append(
                SaleLine(
                    product_id=product_id,
                    name=product.name,
                    sku=product.sku,
                    quantity=quantity,
                    unit_code=unit_code,
                    unit_price=Money(unit_price),
                    discount=Money(line_discount),
                    variant_id=variant_id,
                    branch_id=branch_id,
                    location_code=location_code,
                )
            )

        discount = Money(_decimal(payload.get("discount", "0"), "discount"))
        source = str(payload.get("source", "pos")).strip()
        device_id = str(payload.get("device_id", "")).strip()
        if not source or len(source) > 32:
            raise ValidationError("source must contain 1 to 32 characters")
        if len(device_id) > 128:
            raise ValidationError("device_id cannot exceed 128 characters")

        sale = Sale(
            id=uuid.uuid4(),
            company_id=company_id,
            cashier_id=cashier_id,
            idempotency_key=idempotency_key,
            request_hash=request_hash,
            payment_method=str(payload.get("payment_method", "cash")),
            source=source,
            device_id=device_id,
            discount=discount,
            items=sale_lines,
        )
        sale.validate()

        persisted, created = self.repository.create_or_get(sale)
        if persisted.status == "completed":
            return persisted, False
        if persisted.status == "rejected":
            raise ConflictError("Checkout was rejected", code="checkout_rejected")

        if persisted.inventory_reservation_id is None:
            stock_lines = [
                {
                    "product_id": str(line.product_id),
                    "variant_id": str(line.variant_id) if line.variant_id else None,
                    "branch_id": str(line.branch_id) if line.branch_id else None,
                    "location_code": line.location_code,
                    "quantity": str(line.quantity),
                }
                for line in persisted.items
            ]
            try:
                reservation_id = self.inventory.reserve(
                    company_id,
                    f"sale:{persisted.id}",
                    stock_lines,
                )
            except CRMException as exc:
                if exc.status_code < 500:
                    self.repository.set_status(persisted.id, "rejected")
                raise
            self.repository.set_reservation(persisted.id, reservation_id)
        else:
            reservation_id = persisted.inventory_reservation_id

        try:
            self.inventory.commit(company_id, reservation_id)
        except CRMException:
            raise
        self.repository.set_status(persisted.id, "completed")
        persisted.status = "completed"
        persisted.inventory_reservation_id = reservation_id
        return persisted, created
