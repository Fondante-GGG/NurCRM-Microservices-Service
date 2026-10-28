from decimal import Decimal, InvalidOperation
import uuid

from django.db import IntegrityError, transaction

from backend.services.inventory.domain.models import StockBalance
from backend.services.inventory.infrastructure.models import (
    StockBalanceModel,
    StockMovementModel,
    StockReservationModel,
)
from libs.common.exceptions import ConflictError, NotFoundError, ValidationError


class DjangoInventoryRepository:
    def _to_domain(self, model: StockBalanceModel) -> StockBalance:
        return StockBalance(
            id=model.id,
            company_id=model.company_id,
            product_id=model.product_id,
            variant_id=model.variant_id,
            branch_id=model.branch_id,
            location_code=model.location_code,
            quantity=model.quantity,
            reserved=model.reserved,
        )

    def list_stock(self, company_id, product_id=None, branch_id=None):
        query = StockBalanceModel.objects.filter(company_id=company_id).order_by(
            "product_id", "variant_id", "branch_id", "location_code"
        )
        if product_id is not None:
            query = query.filter(product_id=product_id)
        if branch_id is not None:
            query = query.filter(branch_id=branch_id)
        return [self._to_domain(model) for model in query]

    def _normalise_items(self, items):
        if not isinstance(items, list) or not items or len(items) > 200:
            raise ValidationError("items must contain between 1 and 200 stock lines")

        totals = {}
        for item in items:
            if not isinstance(item, dict):
                raise ValidationError("Each stock line must be an object")
            try:
                product_id = uuid.UUID(str(item["product_id"]))
                variant_id = uuid.UUID(str(item["variant_id"])) if item.get("variant_id") else None
                branch_id = uuid.UUID(str(item["branch_id"])) if item.get("branch_id") else None
                quantity = Decimal(str(item["quantity"]))
            except (KeyError, TypeError, ValueError, InvalidOperation):
                raise ValidationError("Stock lines require valid product_id and quantity values")
            if not quantity.is_finite() or quantity <= 0 or quantity != quantity.quantize(Decimal("0.001")):
                raise ValidationError("Stock quantity must be positive with at most three decimal places")
            location_code = str(item.get("location_code", "default")).strip()
            if not location_code or len(location_code) > 64:
                raise ValidationError("location_code must contain 1 to 64 characters")

            key = (product_id, variant_id, branch_id, location_code)
            totals[key] = totals.get(key, Decimal("0")) + quantity

        return [
            {
                "product_id": str(product_id),
                "variant_id": str(variant_id) if variant_id else None,
                "branch_id": str(branch_id) if branch_id else None,
                "location_code": location_code,
                "quantity": str(quantity),
            }
            for (product_id, variant_id, branch_id, location_code), quantity in sorted(
                totals.items(),
                key=lambda entry: tuple(str(part or "") for part in entry[0]),
            )
        ]

    def _balance_for_update(self, company_id, item):
        scope = {
            "company_id": company_id,
            "product_id": uuid.UUID(item["product_id"]),
            "variant_id": uuid.UUID(item["variant_id"]) if item["variant_id"] else None,
            "branch_id": uuid.UUID(item["branch_id"]) if item["branch_id"] else None,
            "location_code": item["location_code"],
        }
        try:
            model, _ = StockBalanceModel.objects.get_or_create(**scope)
        except IntegrityError:
            model = StockBalanceModel.objects.get(**scope)
        return StockBalanceModel.objects.select_for_update().get(pk=model.pk)

    def reserve(self, company_id, idempotency_key, items):
        if not idempotency_key or len(idempotency_key) > 128:
            raise ValidationError("A valid idempotency_key is required")
        normalized = self._normalise_items(items)

        with transaction.atomic():
            reservation, created = StockReservationModel.objects.get_or_create(
                company_id=company_id,
                idempotency_key=idempotency_key,
                defaults={"items": normalized, "status": "reserved"},
            )
            reservation = StockReservationModel.objects.select_for_update().get(pk=reservation.pk)
            if not created:
                if reservation.items != normalized:
                    raise ConflictError("Idempotency key was already used with different stock lines")
                if reservation.status in ("reserved", "committed"):
                    return reservation.id
                raise ConflictError("Reservation is no longer active", code="reservation_inactive")

            for item in normalized:
                balance = self._to_domain(self._balance_for_update(company_id, item))
                balance.reserve(Decimal(item["quantity"]))
                StockBalanceModel.objects.filter(pk=balance.id).update(reserved=balance.reserved)
            return reservation.id

    def commit_reservation(self, company_id, reservation_id):
        with transaction.atomic():
            reservation = StockReservationModel.objects.select_for_update().filter(
                company_id=company_id, id=reservation_id
            ).first()
            if reservation is None:
                raise NotFoundError(f"Reservation {reservation_id} not found")
            if reservation.status == "committed":
                return
            if reservation.status != "reserved":
                raise ConflictError("Reservation is not active", code="reservation_inactive")

            for index, item in enumerate(reservation.items):
                balance_model = self._balance_for_update(company_id, item)
                balance = self._to_domain(balance_model)
                quantity = Decimal(item["quantity"])
                balance.consume(quantity)
                StockBalanceModel.objects.filter(pk=balance.id).update(
                    quantity=balance.quantity,
                    reserved=balance.reserved,
                )
                source_key = f"reservation:{reservation.id}:{index}"
                StockMovementModel.objects.create(
                    company_id=company_id,
                    product_id=uuid.UUID(item["product_id"]),
                    variant_id=uuid.UUID(item["variant_id"]) if item["variant_id"] else None,
                    branch_id=uuid.UUID(item["branch_id"]) if item["branch_id"] else None,
                    location_code=item["location_code"],
                    movement_type="sale",
                    quantity=quantity,
                    source_key=source_key,
                    reason=f"Reservation {reservation.id}",
                )
            reservation.status = "committed"
            reservation.save(update_fields=("status", "updated_at"))

    def release_reservation(self, company_id, reservation_id):
        with transaction.atomic():
            reservation = StockReservationModel.objects.select_for_update().filter(
                company_id=company_id, id=reservation_id
            ).first()
            if reservation is None:
                raise NotFoundError(f"Reservation {reservation_id} not found")
            if reservation.status == "released":
                return
            if reservation.status != "reserved":
                raise ConflictError("Only active reservations can be released", code="reservation_inactive")

            for item in reservation.items:
                balance_model = self._balance_for_update(company_id, item)
                balance = self._to_domain(balance_model)
                balance.release(Decimal(item["quantity"]))
                StockBalanceModel.objects.filter(pk=balance.id).update(reserved=balance.reserved)
            reservation.status = "released"
            reservation.save(update_fields=("status", "updated_at"))

    def adjust_stock(
        self,
        company_id,
        product_id,
        variant_id,
        branch_id,
        location_code,
        quantity,
        movement_type,
        source_key,
        reason="",
    ):
        if movement_type not in ("receipt", "return", "write_off"):
            raise ValidationError("movement_type must be receipt, return, or write_off")
        if not quantity.is_finite() or quantity <= 0 or quantity != quantity.quantize(Decimal("0.001")):
            raise ValidationError("Stock quantity must be positive with at most three decimal places")
        if source_key and len(source_key) > 128:
            raise ValidationError("source_key cannot exceed 128 characters")
        delta = -quantity if movement_type == "write_off" else quantity
        item = {
            "product_id": str(product_id),
            "variant_id": str(variant_id) if variant_id else None,
            "branch_id": str(branch_id) if branch_id else None,
            "location_code": location_code,
        }

        with transaction.atomic():
            if source_key:
                existing = StockMovementModel.objects.filter(
                    company_id=company_id, source_key=source_key
                ).first()
                if existing:
                    same = (
                        existing.product_id == product_id
                        and existing.variant_id == variant_id
                        and existing.branch_id == branch_id
                        and existing.location_code == location_code
                        and existing.movement_type == movement_type
                        and existing.quantity == quantity
                    )
                    if not same:
                        raise ConflictError("source_key was already used for a different movement")
                    scope = {
                        "company_id": company_id,
                        "product_id": product_id,
                        "variant_id": variant_id,
                        "branch_id": branch_id,
                        "location_code": location_code,
                    }
                    return self._to_domain(StockBalanceModel.objects.get(**scope))

            balance_model = self._balance_for_update(company_id, item)
            balance = self._to_domain(balance_model)
            balance.adjust(delta)
            StockBalanceModel.objects.filter(pk=balance.id).update(quantity=balance.quantity)
            StockMovementModel.objects.create(
                company_id=company_id,
                product_id=product_id,
                variant_id=variant_id,
                branch_id=branch_id,
                location_code=location_code,
                movement_type=movement_type,
                quantity=quantity,
                source_key=source_key,
                reason=reason,
            )
            return balance
