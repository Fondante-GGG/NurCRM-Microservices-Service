from django.urls import path
from backend.services.schedule.interface.views import (
    AppointmentListCreateView,
    AppointmentDetailView,
    MyAppointmentsView,
    ShiftListCreateView,
    ShiftDetailView,
    InternalBusySlotsView,
    InternalAutoCompleteView,
    InternalCreateAppointmentView,
)

urlpatterns = [
    # API v1
    path("api/v1/schedule/appointments/", AppointmentListCreateView.as_view(), name="v1-appointments"),
    path("api/v1/schedule/appointments/my/", MyAppointmentsView.as_view(), name="v1-my-appointments"),
    path("api/v1/schedule/appointments/<uuid:appt_id>/", AppointmentDetailView.as_view(), name="v1-appointment-detail"),

    # TZ tz-beka-support-i-sfery.md endpoints (/api/main/...)
    path("api/main/appointments/", AppointmentListCreateView.as_view(), name="main-appointments"),
    path("api/main/appointments/<uuid:appt_id>/", AppointmentDetailView.as_view(), name="main-appointment-detail"),
    path("api/main/shifts/", ShiftListCreateView.as_view(), name="main-shifts"),
    path("api/main/shifts/<uuid:shift_id>/", ShiftDetailView.as_view(), name="main-shift-detail"),

    # Legacy Aliases (TZ_CRM_SERVICES_SPHERE Section 5)
    path("api/barbershop/appointments/", AppointmentListCreateView.as_view(), name="legacy-appointments"),
    path("api/barbershop/appointments/my/", MyAppointmentsView.as_view(), name="legacy-my-appointments"),
    path("api/barbershop/appointments/<uuid:appt_id>/", AppointmentDetailView.as_view(), name="legacy-appointment-detail"),

    # Internal API
    path("internal/v1/appointments/busy-slots/", InternalBusySlotsView.as_view(), name="internal-busy-slots"),
    path("internal/v1/appointments/auto-complete/", InternalAutoCompleteView.as_view(), name="internal-auto-complete"),
    path("internal/v1/appointments/", InternalCreateAppointmentView.as_view(), name="internal-create-appointment"),
]
