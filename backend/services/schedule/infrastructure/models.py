import uuid
from django.db import models


class AppointmentModel(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company_id = models.UUIDField(db_index=True)
    client_id = models.UUIDField(null=True, blank=True, db_index=True)
    client_name = models.CharField(max_length=255)
    barber_id = models.UUIDField(db_index=True)
    services_snapshot = models.JSONField(default=list)
    start_at = models.DateTimeField(db_index=True)
    end_at = models.DateTimeField(db_index=True)
    price = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    discount = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    status = models.CharField(max_length=32, default="booked", db_index=True)
    comment = models.TextField(blank=True, default="")
    version = models.IntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = '"schedule"."appointments"'
        verbose_name = "Запись"
        verbose_name_plural = "Записи"


class MasterScheduleModel(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company_id = models.UUIDField(db_index=True)
    master_id = models.UUIDField(db_index=True)
    day_of_week = models.IntegerField()
    start_time = models.TimeField(default="09:00:00")
    end_time = models.TimeField(default="21:00:00")
    is_working = models.BooleanField(default=True)

    class Meta:
        db_table = '"schedule"."master_schedules"'
        unique_together = ("company_id", "master_id", "day_of_week")


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
        db_table = '"schedule"."outbox"'


class InboxModel(models.Model):
    event_id = models.UUIDField(primary_key=True)
    event_type = models.CharField(max_length=255)
    processed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = '"schedule"."inbox"'
