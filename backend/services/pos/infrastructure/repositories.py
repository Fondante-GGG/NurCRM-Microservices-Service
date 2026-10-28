import uuid

from django.db import transaction

from backend.services.pos.domain.models import Sale, SaleLine
from backend.services.pos.infrastructure.models import OutboxModel, SaleLineModel, SaleModel
from libs.common.domain import Money
from libs.common.events import EventEnvelope
from libs.common.exceptions import ConflictError, NotFoundError


class DjangoSaleRepository:
    def _to_domain(self, model: SaleModel) -> Sale:
        lines = [
            SaleLine(
                product_id=line.product_id,
                variant_id=line.variant_id,
                branch_id=line.branch_id,
                location_code=line.location_code,
                name=line.name,
                sku=line.sku,
                quantity=line.quantity,
                unit_code=line.unit_code,
                unit_price=Money(line.unit_price),
                discount=Money(line.discount),
            )
            for line in model.items.all()
        ]
        return Sale(
            id=model.id,
            company_id=model.company_id,
            cashier_id=model.cashier_id,
            idempotency_key=model.idempotency_key,
            request_hash=model.request_hash,
            payment_method=model.payment_method,
            source=model.source,
            device_id=model.device_id,
            discount=Money(model.discount),
            status=model.status,
            inventory_reservation_id=model.inventory_reservation_id,
            items=lines,
        )

    def get_by_idempotency_key(
        self,
        company_id: uuid.UUID,
        idempotency_key: str,
        request_hash: str,
    ):
        model = (
            SaleModel.objects.filter(company_id=company_id, idempotency_key=idempotency_key)
            .prefetch_related("items")
            .first()
        )
        if model is None:
            return None
        if model.request_hash != request_hash:
            raise ConflictError("Idempotency key was already used with a different checkout payload")
        return self._to_domain(model)

    def create_or_get(self, sale: Sale):
        with transaction.atomic():
            model, created = SaleModel.objects.get_or_create(
                company_id=sale.company_id,
                idempotency_key=sale.idempotency_key,
                defaults={
                    "id": sale.id,
                    "cashier_id": sale.cashier_id,
                    "branch_id": sale.items[0].branch_id,
                    "request_hash": sale.request_hash,
                    "payment_method": sale.payment_method,
                    "source": sale.source,
                    "device_id": sale.device_id,
                    "discount": sale.discount.amount,
                    "total": sale.total.amount,
                },
            )
            model = SaleModel.objects.select_for_update().get(pk=model.pk)
            if not created and model.request_hash != sale.request_hash:
                raise ConflictError("Idempotency key was already used with a different checkout payload")
            if created:
                SaleLineModel.objects.bulk_create(
                    [
                        SaleLineModel(
                            sale=model,
                            product_id=line.product_id,
                            variant_id=line.variant_id,
                            branch_id=line.branch_id,
                            location_code=line.location_code,
                            name=line.name,
                            sku=line.sku,
                            quantity=line.quantity,
                            unit_code=line.unit_code,
                            unit_price=line.unit_price.amount,
                            discount=line.discount.amount,
                            total=line.total.amount,
                        )
                        for line in sale.items
                    ]
                )
            return self._to_domain(model), created

    def set_reservation(self, sale_id: uuid.UUID, reservation_id: uuid.UUID) -> None:
        updated = SaleModel.objects.filter(id=sale_id, status=SaleModel.Status.PENDING_INVENTORY).update(
            inventory_reservation_id=reservation_id
        )
        if not updated:
            raise NotFoundError(f"Pending sale {sale_id} not found")

    def set_status(self, sale_id: uuid.UUID, status: str) -> None:
        with transaction.atomic():
            sale = SaleModel.objects.select_for_update().filter(id=sale_id).first()
            if sale is None:
                raise NotFoundError(f"Sale {sale_id} not found")
            if sale.status == status:
                return
            if sale.status != SaleModel.Status.PENDING_INVENTORY:
                raise ConflictError(f"Cannot change sale status from {sale.status} to {status}")
            sale.status = status
            sale.save(update_fields=("status", "updated_at"))
            if status == SaleModel.Status.COMPLETED:
                event = EventEnvelope(
                    type="pos.sale.completed",
                    company_id=str(sale.company_id),
                    actor_id=str(sale.cashier_id),
                    data={
                        "sale_id": str(sale.id),
                        "total": str(sale.total),
                        "payment_method": sale.payment_method,
                        "source": sale.source,
                        "branch_id": str(sale.branch_id) if sale.branch_id else None,
                    },
                )
                OutboxModel.objects.create(
                    event_id=uuid.UUID(event.event_id),
                    event_type=event.type,
                    payload=event.to_dict(),
                    status="pending",
                )

    def get_by_id(self, company_id: uuid.UUID, sale_id: uuid.UUID):
        model = SaleModel.objects.filter(company_id=company_id, id=sale_id).prefetch_related("items").first()
        return self._to_domain(model) if model else None

    def list_by_company(self, company_id: uuid.UUID):
        return [
            self._to_domain(model)
            for model in SaleModel.objects.filter(company_id=company_id)
            .order_by("-created_at", "-id")
            .prefetch_related("items")
        ]
