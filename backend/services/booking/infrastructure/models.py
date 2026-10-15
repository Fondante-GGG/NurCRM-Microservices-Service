import uuid
from django.db import models


class BookingRequestModel(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company_id = models.UUIDField(db_index=True)
    client_name = models.CharField(max_length=255)
    client_phone = models.CharField(max_length=32)
    services = models.JSONField(default=list)
    master_id = models.UUIDField(null=True, blank=True, db_index=True)
    date = models.DateField(db_index=True)
    time_start = models.TimeField()
    time_end = models.TimeField()
    total_price = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    total_duration_min = models.IntegerField(default=30)
    payment_method = models.CharField(max_length=32, default="cash")
    client_comment = models.TextField(blank=True, default="")
    status = models.CharField(max_length=32, default="new", db_index=True)
    appointment_id = models.UUIDField(null=True, blank=True)
    confirmed_by = models.CharField(max_length=255, null=True, blank=True)
    version = models.IntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = '"booking"."booking_requests"'
        verbose_name = "Онлайн-заявка"
        verbose_name_plural = "Онлайн-заявки"


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
        db_table = '"booking"."outbox"'


class InboxModel(models.Model):
    event_id = models.UUIDField(primary_key=True)
    event_type = models.CharField(max_length=255)
    processed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = '"booking"."inbox"'
