import uuid
from django.db import models


class AccrualModel(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company_id = models.UUIDField(db_index=True)
    appointment_id = models.UUIDField(unique=True, db_index=True)
    master_id = models.UUIDField(db_index=True)
    service_id = models.UUIDField(null=True, blank=True, db_index=True)
    amount = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    percent = models.DecimalField(max_digits=5, decimal_places=2, default=0.00)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = '"finance"."accruals"'
        verbose_name = "Начисление зарплаты"
        verbose_name_plural = "Начисления зарплаты"


class SalaryPayoutModel(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company_id = models.UUIDField(db_index=True)
    master_id = models.UUIDField(db_index=True)
    amount = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    date = models.DateField()
    cashbox = models.CharField(max_length=64, default="Основная касса")
    comment = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = '"finance"."salary_payouts"'
        verbose_name = "Выплата зарплаты"
        verbose_name_plural = "Выплаты зарплат"


class CashShiftModel(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company_id = models.UUIDField(db_index=True)
    user_id = models.UUIDField(db_index=True)
    cashbox = models.CharField(max_length=64, default="Основная касса")
    opening_cash = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    closing_cash = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    sales_total = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    sales_count = models.IntegerField(default=0)
    status = models.CharField(max_length=32, default="open", db_index=True)
    opened_at = models.DateTimeField(auto_now_add=True)
    closed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = '"finance"."cash_shifts"'
        verbose_name = "Кассовая смена"
        verbose_name_plural = "Кассовые смены"


class WarehouseMaterialModel(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company_id = models.UUIDField(db_index=True)
    name = models.CharField(max_length=255)
    unit = models.CharField(max_length=32, default="шт")
    current_stock = models.DecimalField(max_digits=12, decimal_places=3, default=0.000)
    cost_price = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = '"finance"."warehouse_materials"'


class InventoryMovementModel(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company_id = models.UUIDField(db_index=True)
    material_id = models.UUIDField(db_index=True)
    movement_type = models.CharField(max_length=32)
    quantity = models.DecimalField(max_digits=12, decimal_places=3)
    price = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    reason = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = '"finance"."inventory_movements"'


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
        db_table = '"finance"."outbox"'


class InboxModel(models.Model):
    event_id = models.UUIDField(primary_key=True)
    event_type = models.CharField(max_length=255)
    processed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = '"finance"."inbox"'
