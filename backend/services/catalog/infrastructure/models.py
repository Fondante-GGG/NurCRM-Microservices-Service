import uuid
from django.db import models


from django.contrib.postgres.fields import ArrayField


class ServiceCategoryModel(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company_id = models.UUIDField(db_index=True)
    name = models.CharField(max_length=255)
    is_active = models.BooleanField(default=True)
    version = models.IntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = '"catalog"."service_categories"'
        verbose_name = "Категория услуг"
        verbose_name_plural = "Категории услуг"


class ServiceModel(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company_id = models.UUIDField(db_index=True)
    category_id = models.UUIDField(db_index=True)
    name = models.CharField(max_length=255)
    price = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    time_minutes = models.IntegerField(default=30)
    barbers = ArrayField(models.UUIDField(), default=list, blank=True)
    is_active = models.BooleanField(default=True)
    version = models.IntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = '"catalog"."services"'
        verbose_name = "Услуга"
        verbose_name_plural = "Услуги"


class SalaryRateModel(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company_id = models.UUIDField(db_index=True)
    service_id = models.UUIDField(db_index=True)
    master_id = models.UUIDField(null=True, blank=True, db_index=True)
    percent = models.DecimalField(max_digits=5, decimal_places=2, default=0.00)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = '"catalog"."salary_rates"'
        unique_together = ("company_id", "service_id", "master_id")
        verbose_name = "Ставка зарплаты"
        verbose_name_plural = "Ставки зарплат"


class ProductModel(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company_id = models.UUIDField(db_index=True)
    name = models.CharField(max_length=255)
    sku = models.CharField(max_length=64, blank=True, default="")
    category = models.CharField(max_length=255, blank=True, default="")
    price = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    cost_price = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    wholesale_price = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    unit_code = models.CharField(max_length=32, default="pcs")
    minimum_quantity = models.DecimalField(max_digits=12, decimal_places=3, default=1)
    quantity_step = models.DecimalField(max_digits=12, decimal_places=3, default=1)
    attributes = models.JSONField(default=dict, blank=True)
    is_active = models.BooleanField(default=True)
    version = models.IntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = '"catalog"."products"'
        constraints = [
            models.UniqueConstraint(
                fields=("company_id", "sku"),
                condition=~models.Q(sku=""),
                name="uq_catalog_product_company_sku",
            ),
            models.CheckConstraint(condition=models.Q(price__gte=0), name="ck_catalog_product_price_nonnegative"),
            models.CheckConstraint(condition=models.Q(cost_price__gte=0), name="ck_catalog_product_cost_nonnegative"),
            models.CheckConstraint(condition=models.Q(quantity_step__gt=0), name="ck_catalog_product_step_positive"),
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
        db_table = '"catalog"."outbox"'


class InboxModel(models.Model):
    event_id = models.UUIDField(primary_key=True)
    event_type = models.CharField(max_length=255)
    processed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = '"catalog"."inbox"'
