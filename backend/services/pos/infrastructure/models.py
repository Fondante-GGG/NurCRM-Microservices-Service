import uuid

from django.db import models


class SaleModel(models.Model):
    class Status(models.TextChoices):
        PENDING_INVENTORY = "pending_inventory", "Pending inventory"
        COMPLETED = "completed", "Completed"
        REJECTED = "rejected", "Rejected"
        RETURNED = "returned", "Returned"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company_id = models.UUIDField(db_index=True)
    cashier_id = models.UUIDField(db_index=True)
    branch_id = models.UUIDField(null=True, blank=True)
    idempotency_key = models.CharField(max_length=128)
    request_hash = models.CharField(max_length=64)
    inventory_reservation_id = models.UUIDField(null=True, blank=True)
    payment_method = models.CharField(max_length=32, default="cash")
    source = models.CharField(max_length=32, default="pos")
    device_id = models.CharField(max_length=128, blank=True, default="")
    discount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    status = models.CharField(max_length=32, choices=Status.choices, default=Status.PENDING_INVENTORY)
    sold_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = '"pos"."sales"'
        constraints = [
            models.UniqueConstraint(
                fields=("company_id", "idempotency_key"),
                name="uq_pos_sale_idempotency",
            ),
            models.CheckConstraint(condition=models.Q(discount__gte=0), name="ck_pos_sale_discount_nonnegative"),
            models.CheckConstraint(condition=models.Q(total__gte=0), name="ck_pos_sale_total_nonnegative"),
        ]
        indexes = [models.Index(fields=("company_id", "created_at"))]


class SaleLineModel(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    sale = models.ForeignKey(SaleModel, on_delete=models.CASCADE, related_name="items")
    product_id = models.UUIDField(db_index=True)
    variant_id = models.UUIDField(null=True, blank=True)
    branch_id = models.UUIDField(null=True, blank=True)
    location_code = models.CharField(max_length=64, default="default")
    name = models.CharField(max_length=255)
    sku = models.CharField(max_length=64, blank=True, default="")
    quantity = models.DecimalField(max_digits=12, decimal_places=3)
    unit_code = models.CharField(max_length=32)
    unit_price = models.DecimalField(max_digits=12, decimal_places=2)
    discount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=12, decimal_places=2)

    class Meta:
        db_table = '"pos"."sale_lines"'
        constraints = [
            models.CheckConstraint(condition=models.Q(quantity__gt=0), name="ck_pos_line_quantity_positive"),
            models.CheckConstraint(condition=models.Q(unit_price__gte=0), name="ck_pos_line_price_nonnegative"),
            models.CheckConstraint(condition=models.Q(discount__gte=0), name="ck_pos_line_discount_nonnegative"),
            models.CheckConstraint(condition=models.Q(total__gte=0), name="ck_pos_line_total_nonnegative"),
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
        db_table = '"pos"."outbox"'


class InboxModel(models.Model):
    event_id = models.UUIDField(primary_key=True)
    event_type = models.CharField(max_length=255)
    processed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = '"pos"."inbox"'
