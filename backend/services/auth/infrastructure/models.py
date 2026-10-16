import uuid
from django.db import models


class CompanyModel(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=128, unique=True)
    industry = models.CharField(max_length=128, null=True, blank=True)
    intake = models.CharField(max_length=32, default="schedule")
    sector = models.CharField(max_length=128, default="Услуги")
    legal_name = models.CharField(max_length=255, default="", blank=True)
    inn = models.CharField(max_length=32, default="", blank=True)
    okpo = models.CharField(max_length=32, default="", blank=True)
    account = models.CharField(max_length=64, default="", blank=True)
    bik = models.CharField(max_length=32, default="", blank=True)
    address = models.TextField(default="", blank=True)
    phones = models.JSONField(default=list, blank=True)
    blocked = models.BooleanField(default=False)
    plan = models.CharField(max_length=32, default="free")
    temp_access_until = models.DateTimeField(null=True, blank=True)
    appointment_work_start = models.TimeField(default="09:00:00")
    appointment_work_end = models.TimeField(default="21:00:00")
    subscription_plan = models.CharField(max_length=64, default="Стандарт")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = '"auth"."companies"'
        verbose_name = "Компания"
        verbose_name_plural = "Компании"


class BranchModel(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company_id = models.UUIDField(db_index=True)
    name = models.CharField(max_length=255)
    address = models.TextField(default="", blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = '"auth"."branches"'
        verbose_name = "Филиал"
        verbose_name_plural = "Филиалы"


class SupportTicketModel(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company_id = models.UUIDField(db_index=True)
    topic = models.CharField(max_length=64)
    message = models.TextField()
    contact = models.CharField(max_length=64)
    share_access = models.BooleanField(default=False)
    status = models.CharField(max_length=32, default="new", db_index=True)
    assignee = models.CharField(max_length=255, default="", blank=True)
    reply = models.TextField(default="", blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = '"auth"."support_tickets"'
        verbose_name = "Обращение в поддержку"
        verbose_name_plural = "Обращения в поддержку"


class SupportLogModel(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    at = models.DateTimeField(auto_now_add=True)
    agent = models.CharField(max_length=255)
    company_id = models.UUIDField(db_index=True)
    action = models.TextField()

    class Meta:
        db_table = '"auth"."support_log"'
        verbose_name = "Журнал действий поддержки"
        verbose_name_plural = "Журнал действий поддержки"


from django.contrib.postgres.fields import ArrayField


class EmployeeModel(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company_id = models.UUIDField(db_index=True)
    first_name = models.CharField(max_length=128)
    last_name = models.CharField(max_length=128)
    email = models.EmailField(max_length=255)
    password_hash = models.CharField(max_length=255)
    phone_number = models.CharField(max_length=32)
    role = models.CharField(max_length=32, default="master")
    role_display = models.CharField(max_length=128, default="Специалист")
    avatar = models.CharField(max_length=512, null=True, blank=True)
    branch_ids = ArrayField(models.UUIDField(), default=list, blank=True)
    is_active = models.BooleanField(default=True)
    version = models.IntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = '"auth"."employees"'
        unique_together = ("company_id", "email")
        verbose_name = "Сотрудник"
        verbose_name_plural = "Сотрудники"


class SessionModel(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company_id = models.UUIDField(db_index=True)
    user_id = models.UUIDField(db_index=True)
    device = models.CharField(max_length=255, null=True, blank=True)
    ip_address = models.CharField(max_length=45, null=True, blank=True)
    refresh_token_hash = models.CharField(max_length=255)
    is_revoked = models.BooleanField(default=False)
    last_seen = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = '"auth"."sessions"'
        verbose_name = "Сессия"
        verbose_name_plural = "Сессии"


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
        db_table = '"auth"."outbox"'


class InboxModel(models.Model):
    event_id = models.UUIDField(primary_key=True)
    event_type = models.CharField(max_length=255)
    processed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = '"auth"."inbox"'
