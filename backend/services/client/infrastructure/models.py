import uuid
from django.db import models


class ClientModel(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company_id = models.UUIDField(db_index=True)
    full_name = models.CharField(max_length=255)
    phone = models.CharField(max_length=32)
    birth_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=32, default="active")
    notes = models.TextField(null=True, blank=True)
    version = models.IntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = '"clients"."clients"'
        unique_together = ("company_id", "phone")
        verbose_name = "Клиент"
        verbose_name_plural = "Клиенты"


class ClientDocumentModel(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company_id = models.UUIDField(db_index=True)
    client_id = models.UUIDField(db_index=True)
    file_path = models.CharField(max_length=512)
    file_name = models.CharField(max_length=255)
    file_size = models.IntegerField()
    file_comment = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = '"clients"."client_documents"'
        verbose_name = "Документ клиента"
        verbose_name_plural = "Документы клиентов"


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
        db_table = '"clients"."outbox"'


class InboxModel(models.Model):
    event_id = models.UUIDField(primary_key=True)
    event_type = models.CharField(max_length=255)
    processed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = '"clients"."inbox"'
