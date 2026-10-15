import uuid
from django.db import models


# Schema: auth
class AdminCompany(models.Model):
    id = models.UUIDField(primary_key=True)
    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=128)
    industry = models.CharField(max_length=128)
    sector = models.CharField(max_length=128)
    appointment_work_start = models.TimeField()
    appointment_work_end = models.TimeField()
    subscription_plan = models.CharField(max_length=64)
    created_at = models.DateTimeField()

    class Meta:
        managed = False
        db_table = '"auth"."companies"'
        app_label = "admin_auth"
        verbose_name = "Компания"
        verbose_name_plural = "Компании"

    def __str__(self):
        return self.name


class AdminEmployee(models.Model):
    id = models.UUIDField(primary_key=True)
    company_id = models.UUIDField()
    first_name = models.CharField(max_length=128)
    last_name = models.CharField(max_length=128)
    email = models.EmailField(max_length=255)
    phone_number = models.CharField(max_length=32)
    role = models.CharField(max_length=32)
    role_display = models.CharField(max_length=128)
    is_active = models.BooleanField()
    created_at = models.DateTimeField()

    class Meta:
        managed = False
        db_table = '"auth"."employees"'
        app_label = "admin_auth"
        verbose_name = "Сотрудник"
        verbose_name_plural = "Сотрудники"

    def __str__(self):
        return f"{self.first_name} {self.last_name} ({self.role})"


# Schema: catalog
class AdminServiceCategory(models.Model):
    id = models.UUIDField(primary_key=True)
    company_id = models.UUIDField()
    name = models.CharField(max_length=255)
    is_active = models.BooleanField()

    class Meta:
        managed = False
        db_table = '"catalog"."service_categories"'
        app_label = "admin_catalog"
        verbose_name = "Категория услуг"
        verbose_name_plural = "Категории услуг"

    def __str__(self):
        return self.name


class AdminService(models.Model):
    id = models.UUIDField(primary_key=True)
    company_id = models.UUIDField()
    category_id = models.UUIDField()
    name = models.CharField(max_length=255)
    price = models.DecimalField(max_digits=12, decimal_places=2)
    time_minutes = models.IntegerField()
    is_active = models.BooleanField()

    class Meta:
        managed = False
        db_table = '"catalog"."services"'
        app_label = "admin_catalog"
        verbose_name = "Услуга"
        verbose_name_plural = "Услуги"

    def __str__(self):
        return f"{self.name} ({self.price} KGS)"


# Schema: clients
class AdminClient(models.Model):
    id = models.UUIDField(primary_key=True)
    company_id = models.UUIDField()
    full_name = models.CharField(max_length=255)
    phone = models.CharField(max_length=32)
    birth_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=32)
    notes = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField()

    class Meta:
        managed = False
        db_table = '"clients"."clients"'
        app_label = "admin_clients"
        verbose_name = "Клиент"
        verbose_name_plural = "Клиенты"

    def __str__(self):
        return f"{self.full_name} ({self.phone})"


# Schema: schedule (Critical - Read Only)
class AdminAppointment(models.Model):
    id = models.UUIDField(primary_key=True)
    company_id = models.UUIDField()
    client_name = models.CharField(max_length=255)
    barber_id = models.UUIDField()
    start_at = models.DateTimeField()
    end_at = models.DateTimeField()
    price = models.DecimalField(max_digits=12, decimal_places=2)
    status = models.CharField(max_length=32)
    comment = models.TextField()
    version = models.IntegerField()
    created_at = models.DateTimeField()

    class Meta:
        managed = False
        db_table = '"schedule"."appointments"'
        app_label = "admin_schedule"
        verbose_name = "Запись"
        verbose_name_plural = "Записи"

    def __str__(self):
        return f"Запись #{str(self.id)[:8]} - {self.client_name} ({self.status})"


# Schema: booking
class AdminBookingRequest(models.Model):
    id = models.UUIDField(primary_key=True)
    company_id = models.UUIDField()
    client_name = models.CharField(max_length=255)
    client_phone = models.CharField(max_length=32)
    date = models.DateField()
    time_start = models.TimeField()
    total_price = models.DecimalField(max_digits=12, decimal_places=2)
    status = models.CharField(max_length=32)
    created_at = models.DateTimeField()

    class Meta:
        managed = False
        db_table = '"booking"."booking_requests"'
        app_label = "admin_booking"
        verbose_name = "Онлайн-заявка"
        verbose_name_plural = "Онлайн-заявки"


# Schema: finance (Critical - Read Only)
class AdminAccrual(models.Model):
    id = models.UUIDField(primary_key=True)
    company_id = models.UUIDField()
    appointment_id = models.UUIDField()
    master_id = models.UUIDField()
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    percent = models.DecimalField(max_digits=5, decimal_places=2)
    created_at = models.DateTimeField()

    class Meta:
        managed = False
        db_table = '"finance"."accruals"'
        app_label = "admin_finance"
        verbose_name = "Начисление зарплаты"
        verbose_name_plural = "Начисления зарплат"


class AdminCashShift(models.Model):
    id = models.UUIDField(primary_key=True)
    company_id = models.UUIDField()
    cashbox = models.CharField(max_length=64)
    opening_cash = models.DecimalField(max_digits=12, decimal_places=2)
    closing_cash = models.DecimalField(max_digits=12, decimal_places=2, null=True)
    sales_total = models.DecimalField(max_digits=12, decimal_places=2)
    status = models.CharField(max_length=32)
    opened_at = models.DateTimeField()

    class Meta:
        managed = False
        db_table = '"finance"."cash_shifts"'
        app_label = "admin_finance"
        verbose_name = "Кассовая смена"
        verbose_name_plural = "Кассовые смены"


# Schema: admin (Audit Log)
class AuditLogModel(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    actor_id = models.UUIDField(null=True, blank=True)
    company_id = models.UUIDField(null=True, blank=True)
    service = models.CharField(max_length=64)
    action = models.CharField(max_length=64)
    entity_type = models.CharField(max_length=64)
    entity_id = models.UUIDField(null=True, blank=True)
    before_state = models.JSONField(null=True, blank=True)
    after_state = models.JSONField(null=True, blank=True)
    ip_address = models.CharField(max_length=45, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        managed = False
        db_table = '"admin"."audit_logs"'
        app_label = "admin_audit"
        verbose_name = "Аудит-лог"
        verbose_name_plural = "Аудит-логи"
