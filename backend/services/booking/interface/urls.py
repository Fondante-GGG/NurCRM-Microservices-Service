from django.urls import path
from backend.services.booking.interface.views import (
    BookingListCreateView,
    BookingDetailView,
    InternalBookingCreateView,
)

urlpatterns = [
    # API v1
    path("api/v1/bookings/", BookingListCreateView.as_view(), name="v1-bookings"),
    path("api/v1/bookings/<uuid:booking_id>/", BookingDetailView.as_view(), name="v1-booking-detail"),

    # Legacy Aliases (TZ_CRM_SERVICES_SPHERE Section 5)
    path("api/barbershop/bookings/", BookingListCreateView.as_view(), name="legacy-bookings"),
    path("api/barbershop/bookings/<uuid:booking_id>/", BookingDetailView.as_view(), name="legacy-booking-detail"),

    # Internal API
    path("internal/v1/bookings/", InternalBookingCreateView.as_view(), name="internal-create-booking"),
]
