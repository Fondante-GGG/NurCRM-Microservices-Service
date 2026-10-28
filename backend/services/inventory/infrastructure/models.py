import uuid

from django.db import models


class StockBalanceModel(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company_id = models.UUIDField(db_index=True)
    product_id = models.UUIDField(db_index=True)
    variant_id = models.UUIDField(null=True, blank=True)
    branch_id = models.UUIDField(null=True, blank=True)
    location_code = models.CharField(max_length=64, default="default")
    quantity = models.DecimalField(max_digits=14, decimal_places=3, default=0)
    reserved = models.DecimalField(max_digits=14, decimal_places=3, default=0)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = '"inventory"."stock_balances"'
        constraints = [
            models.UniqueConstraint(
                fields=("company_id", "product_id", "variant_id", "branch_id", "location_code"),
                nulls_distinct=False,
                name="uq_inventory_stock_scope",
            ),
            models.CheckConstraint(condition=models.Q(quantity__gte=0), name="ck_inventory_quantity_nonnegative"),
            models.CheckConstraint(condition=models.Q(reserved__gte=0), name="ck_inventory_reserved_nonnegative"),
            models.CheckConstraint(condition=models.Q(reserved__lte=models.F("quantity")), name="ck_inventory_reserved_lte_quantity"),
        ]


class StockMovementModel(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company_id = models.UUIDField(db_index=True)
    product_id = models.UUIDField(db_index=True)
    variant_id = models.UUIDField(null=True, blank=True)
    branch_id = models.UUIDField(null=True, blank=True)
    location_code = models.CharField(max_length=64, default="default")
    movement_type = models.CharField(max_length=32)
    quantity = models.DecimalField(max_digits=14, decimal_places=3)
    source_key = models.CharField(max_length=128, blank=True, default="")
    reason = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = '"inventory"."stock_movements"'
        indexes = [models.Index(fields=("company_id", "product_id", "created_at"))]
        constraints = [
            models.UniqueConstraint(
                fields=("company_id", "source_key"),
                condition=~models.Q(source_key=""),
                name="uq_inventory_movement_source",
            ),
        ]


class StockReservationModel(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company_id = models.UUIDField(db_index=True)
    idempotency_key = models.CharField(max_length=128)
    status = models.CharField(max_length=16, default="reserved")
    items = models.JSONField(default=list)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = '"inventory"."stock_reservations"'
        constraints = [
            models.UniqueConstraint(
                fields=("company_id", "idempotency_key"),
                name="uq_inventory_reservation_idempotency",
            ),
        ]


class OutboxModel(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    event_id = models.UUIDField()
    event_type = models.CharField(max_length=255)
    payload = models.JSONField()
    status = models.CharField(max_length=32, default="pending")
    retry_count = models.IntegerField(default=0)
    error = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    published_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = '"inventory"."outbox"'


class InboxModel(models.Model):
    event_id = models.UUIDField(primary_key=True)
    event_type = models.CharField(max_length=255)
    processed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = '"inventory"."inbox"'
