from django.urls import path

from backend.services.inventory.interface.views import (
    InternalReservationActionView,
    InternalReservationView,
    StockListView,
    StockMovementCreateView,
)

urlpatterns = [
    path("api/v1/inventory/stock/", StockListView.as_view(), name="inventory-stock"),
    path("api/v1/inventory/movements/", StockMovementCreateView.as_view(), name="inventory-movements"),
    path("api/main/warehouse/stock/", StockListView.as_view(), name="legacy-inventory-stock"),
    path("api/main/warehouse/movements/", StockMovementCreateView.as_view(), name="legacy-inventory-movements"),
    path("internal/v1/reservations/", InternalReservationView.as_view(), name="internal-reservations"),
    path(
        "internal/v1/reservations/<uuid:reservation_id>/<str:action>/",
        InternalReservationActionView.as_view(),
        name="internal-reservation-action",
    ),
]
