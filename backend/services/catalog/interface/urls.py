from django.urls import path
from backend.services.catalog.interface.views import (
    CategoryListCreateView,
    CategoryDetailView,
    ServiceListCreateView,
    ServiceDetailView,
    SalaryRatesView,
    InternalServicesView,
    InternalRateView,
    InternalCategoriesView,
)

urlpatterns = [
    # API v1
    path("api/v1/catalog/categories/", CategoryListCreateView.as_view(), name="v1-categories"),
    path("api/v1/catalog/categories/<uuid:category_id>/", CategoryDetailView.as_view(), name="v1-category-detail"),
    path("api/v1/catalog/services/", ServiceListCreateView.as_view(), name="v1-services"),
    path("api/v1/catalog/services/<uuid:service_id>/", ServiceDetailView.as_view(), name="v1-service-detail"),
    path("api/v1/catalog/rates/", SalaryRatesView.as_view(), name="v1-rates"),
    path("api/v1/catalog/rates/<uuid:service_id>/", SalaryRatesView.as_view(), name="v1-rate-detail"),

    # Legacy Aliases (TZ_CRM_SERVICES_SPHERE Section 5)
    path("api/barbershop/service-categories/", CategoryListCreateView.as_view(), name="legacy-categories"),
    path("api/barbershop/service-categories/<uuid:category_id>/", CategoryDetailView.as_view(), name="legacy-category-detail"),
    path("api/barbershop/services/", ServiceListCreateView.as_view(), name="legacy-services"),
    path("api/barbershop/services/<uuid:service_id>/", ServiceDetailView.as_view(), name="legacy-service-detail"),
    path("api/barbershop/salary/rates/", SalaryRatesView.as_view(), name="legacy-rates"),
    path("api/barbershop/salary/rates/<uuid:service_id>/", SalaryRatesView.as_view(), name="legacy-rate-detail"),

    # Internal API
    path("internal/v1/categories/", InternalCategoriesView.as_view(), name="internal-categories"),
    path("internal/v1/services/", InternalServicesView.as_view(), name="internal-services"),
    path("internal/v1/rates/<uuid:service_id>/", InternalRateView.as_view(), name="internal-rate"),
]
