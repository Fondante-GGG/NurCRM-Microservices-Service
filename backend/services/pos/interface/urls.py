from django.urls import path

from backend.services.pos.interface.views import SaleDetailView, SaleListCreateView

urlpatterns = [
    path("api/v1/pos/sales/", SaleListCreateView.as_view(), name="pos-sales"),
    path("api/v1/pos/sales/<uuid:sale_id>/", SaleDetailView.as_view(), name="pos-sale-detail"),
    path("api/main/pos/checkout/", SaleListCreateView.as_view(), name="legacy-pos-checkout"),
    path("api/main/pos/sales/", SaleListCreateView.as_view(), name="legacy-pos-sales"),
    path("api/main/pos/sales/<uuid:sale_id>/", SaleDetailView.as_view(), name="legacy-pos-sale-detail"),
]
