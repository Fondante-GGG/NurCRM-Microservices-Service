from django.urls import path
from backend.services.finance.interface.views import (
    ShiftListCreateView,
    ShiftCloseView,
    SalaryAccrualsView,
    SalaryPayoutsView,
    SalarySummaryView,
    WarehouseMaterialsView,
    InternalProcessCompletedAppointmentView,
)

urlpatterns = [
    # API v1
    path("api/v1/finance/shifts/", ShiftListCreateView.as_view(), name="v1-shifts"),
    path("api/v1/finance/shifts/<uuid:shift_id>/close/", ShiftCloseView.as_view(), name="v1-shift-close"),
    path("api/v1/finance/salary/accruals/", SalaryAccrualsView.as_view(), name="v1-accruals"),
    path("api/v1/finance/salary/payouts/", SalaryPayoutsView.as_view(), name="v1-payouts"),
    path("api/v1/finance/salary/summary/", SalarySummaryView.as_view(), name="v1-salary-summary"),
    path("api/v1/finance/warehouse/materials/", WarehouseMaterialsView.as_view(), name="v1-warehouse-materials"),

    # Legacy Aliases (TZ_CRM_SERVICES_SPHERE Section 5)
    path("api/construction/shifts/", ShiftListCreateView.as_view(), name="legacy-shifts"),
    path("api/construction/shifts/<uuid:shift_id>/close/", ShiftCloseView.as_view(), name="legacy-shift-close"),
    path("api/barbershop/salary/accruals/", SalaryAccrualsView.as_view(), name="legacy-accruals"),
    path("api/barbershop/salary/payouts/", SalaryPayoutsView.as_view(), name="legacy-payouts"),
    path("api/barbershop/salary/summary/", SalarySummaryView.as_view(), name="legacy-salary-summary"),

    # Internal API
    path("internal/v1/finance/accruals/process-completed/", InternalProcessCompletedAppointmentView.as_view(), name="internal-process-completed"),
]
