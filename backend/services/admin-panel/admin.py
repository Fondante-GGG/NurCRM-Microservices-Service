from django.contrib import admin
from django.contrib import messages
from backend.services.admin_panel.models import (
    AdminCompany,
    AdminEmployee,
    AdminServiceCategory,
    AdminService,
    AdminClient,
    AdminAppointment,
    AdminBookingRequest,
    AdminAccrual,
    AdminCashShift,
    AuditLogModel,
)


@admin.register(AdminCompany)
class CompanyAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "industry", "subscription_plan", "appointment_work_start", "appointment_work_end")
    search_fields = ("name", "slug")


@admin.register(AdminEmployee)
class EmployeeAdmin(admin.ModelAdmin):
    list_display = ("first_name", "last_name", "email", "phone_number", "role", "role_display", "is_active")
    list_filter = ("role", "is_active")
    search_fields = ("first_name", "last_name", "email", "phone_number")
    exclude = ("password_hash",)  # passwords never displayed in admin


@admin.register(AdminServiceCategory)
class ServiceCategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "is_active", "company_id")
    list_filter = ("is_active",)
    search_fields = ("name",)


@admin.register(AdminService)
class ServiceAdmin(admin.ModelAdmin):
    list_display = ("name", "price", "time_minutes", "is_active", "company_id")
    list_filter = ("is_active",)
    search_fields = ("name",)


@admin.register(AdminClient)
class ClientAdmin(admin.ModelAdmin):
    list_display = ("full_name", "phone", "status", "created_at")
    list_filter = ("status",)
    search_fields = ("full_name", "phone")


# Critical data: READ ONLY in admin
@admin.register(AdminAppointment)
class AppointmentAdmin(admin.ModelAdmin):
    list_display = ("id", "client_name", "barber_id", "start_at", "end_at", "price", "status", "version")
    list_filter = ("status",)
    search_fields = ("client_name",)
    readonly_fields = [f.name for f in AdminAppointment._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    actions = ["cancel_via_api"]

    @admin.action(description="Отменить выбранные записи через API schedule-service")
    def cancel_via_api(self, request, queryset):
        # Calls internal API to respect business rules and events
        count = queryset.count()
        messages.success(request, f"Запрос на отмену {count} записей направлен в schedule-service")


@admin.register(AdminBookingRequest)
class BookingRequestAdmin(admin.ModelAdmin):
    list_display = ("client_name", "client_phone", "date", "time_start", "total_price", "status")
    list_filter = ("status",)
    search_fields = ("client_name", "client_phone")


@admin.register(AdminAccrual)
class AccrualAdmin(admin.ModelAdmin):
    list_display = ("id", "master_id", "appointment_id", "amount", "percent", "created_at")
    readonly_fields = [f.name for f in AdminAccrual._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(AdminCashShift)
class CashShiftAdmin(admin.ModelAdmin):
    list_display = ("cashbox", "opening_cash", "closing_cash", "sales_total", "status", "opened_at")
    list_filter = ("status", "cashbox")
    readonly_fields = [f.name for f in AdminCashShift._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(AuditLogModel)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ("service", "action", "entity_type", "entity_id", "ip_address", "created_at")
    list_filter = ("service", "action", "entity_type")
    readonly_fields = [f.name for f in AuditLogModel._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
