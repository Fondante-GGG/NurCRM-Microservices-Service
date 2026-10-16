from django.urls import path, re_path
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
from backend.services.auth.interface.support_and_spheres_views import (
    MainCompanyView,
    MainCompanyIndustryView,
    MainCompanyTempAccessView,
    MainBranchesView,
    MeView,
    MainSupportTicketsView,
    MainAuditView,
    SupportCompaniesListView,
    SupportCompanyDetailView,
    SupportCompanyBranchesView,
    SupportCompanyTempAccessView,
    SupportCompanyResetPasswordView,
    SupportTicketsListView,
    SupportTicketDetailView,
    SupportLogView,
    SupportImpersonateView,
    SupportImpersonateExitView,
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
    path("api/v1/auth/me/", MeView.as_view(), name="v1-me"),

    # TZ tz-beka-support-i-sfery.md endpoints (/api/main/...)
    path("api/main/company/", MainCompanyView.as_view(), name="main-company"),
    path("api/main/company/industry/", MainCompanyIndustryView.as_view(), name="main-company-industry"),
    path("api/main/company/temp-access/", MainCompanyTempAccessView.as_view(), name="main-company-temp-access"),
    path("api/main/branches/", MainBranchesView.as_view(), name="main-branches"),
    path("api/main/support/tickets/", MainSupportTicketsView.as_view(), name="main-support-tickets"),
    path("api/main/audit/", MainAuditView.as_view(), name="main-audit"),
    re_path(r"^api/main/me/?$", MeView.as_view(), name="main-me"),
    re_path(r"^me/?$", MeView.as_view(), name="root-me"),

    # Support Panel (/api/support/...)
    path("api/support/companies/", SupportCompaniesListView.as_view(), name="support-companies-list"),
    path("api/support/companies/<uuid:id>/", SupportCompanyDetailView.as_view(), name="support-company-detail"),
    path("api/support/companies/<uuid:id>/branches/", SupportCompanyBranchesView.as_view(), name="support-company-branches-add"),
    path("api/support/companies/<uuid:id>/branches/<uuid:bid>/", SupportCompanyBranchesView.as_view(), name="support-company-branches-del"),
    path("api/support/companies/<uuid:id>/temp-access/", SupportCompanyTempAccessView.as_view(), name="support-company-temp-access"),
    path("api/support/companies/<uuid:id>/reset-password/", SupportCompanyResetPasswordView.as_view(), name="support-company-reset-password"),
    path("api/support/companies/<uuid:id>/impersonate/", SupportImpersonateView.as_view(), name="support-company-impersonate"),
    path("api/support/impersonate/exit/", SupportImpersonateExitView.as_view(), name="support-impersonate-exit"),
    path("api/support/tickets/", SupportTicketsListView.as_view(), name="support-tickets-list"),
    path("api/support/tickets/<uuid:id>/", SupportTicketDetailView.as_view(), name="support-ticket-detail"),
    path("api/support/log/", SupportLogView.as_view(), name="support-log"),

    # Legacy Aliases (TZ_CRM_SERVICES_SPHERE section 5)
    path("api/users/auth/login/", LoginView.as_view(), name="legacy-login"),
    path("api/users/auth/refresh/", RefreshView.as_view(), name="legacy-refresh"),
    path("api/users/profile/", ProfileView.as_view(), name="legacy-profile"),
    path("api/users/company/", CompanyView.as_view(), name="legacy-company"),

    # Internal API
    path("internal/v1/companies/<uuid:company_id>/", InternalCompanyView.as_view(), name="internal-company-by-id"),
    path("internal/v1/companies/slug/<str:slug>/", InternalCompanyView.as_view(), name="internal-company-by-slug"),
    path("internal/v1/masters/", InternalMastersView.as_view(), name="internal-masters"),
]
