from django.urls import path
from backend.services.auth.interface.views import (
    JWKSView,
    LoginView,
    RefreshView,
    ProfileView,
    CompanyView,
    EmployeeListView,
    InternalCompanyView,
    InternalMastersView,
)

urlpatterns = [
    # JWKS
    path(".well-known/jwks.json", JWKSView.as_view(), name="jwks"),

    # API v1
    path("api/v1/auth/login/", LoginView.as_view(), name="v1-login"),
    path("api/v1/auth/refresh/", RefreshView.as_view(), name="v1-refresh"),
    path("api/v1/auth/profile/", ProfileView.as_view(), name="v1-profile"),
    path("api/v1/auth/company/", CompanyView.as_view(), name="v1-company"),
    path("api/v1/auth/employees/", EmployeeListView.as_view(), name="v1-employees"),

    # Legacy Aliases (TZ_CRM_SERVICES_SPHERE section 5)
    path("api/users/auth/login/", LoginView.as_view(), name="legacy-login"),
    path("api/users/auth/refresh/", RefreshView.as_view(), name="legacy-refresh"),
    path("api/users/profile/", ProfileView.as_view(), name="legacy-profile"),
    path("api/users/company/", CompanyView.as_view(), name="legacy-company"),

    # Internal API (Section 5)
    path("internal/v1/companies/<uuid:company_id>/", InternalCompanyView.as_view(), name="internal-company-by-id"),
    path("internal/v1/companies/slug/<str:slug>/", InternalCompanyView.as_view(), name="internal-company-by-slug"),
    path("internal/v1/masters/", InternalMastersView.as_view(), name="internal-masters"),
]
