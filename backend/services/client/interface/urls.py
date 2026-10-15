from django.urls import path
from backend.services.client.interface.views import (
    ClientListCreateView,
    ClientDetailView,
    ClientDocumentsView,
    ClientDocumentDetailView,
    ClientDocumentDownloadView,
    ClientVisitsHistoryView,
    InternalFindOrCreateClientView,
    InternalClientDetailView,
)

urlpatterns = [
    # API v1
    path("api/v1/clients/", ClientListCreateView.as_view(), name="v1-clients"),
    path("api/v1/clients/<uuid:client_id>/", ClientDetailView.as_view(), name="v1-client-detail"),
    path("api/v1/clients/<uuid:client_id>/documents/", ClientDocumentsView.as_view(), name="v1-client-docs"),
    path("api/v1/clients/<uuid:client_id>/documents/<uuid:doc_id>/", ClientDocumentDetailView.as_view(), name="v1-client-doc-detail"),
    path("api/v1/clients/<uuid:client_id>/documents/<uuid:doc_id>/download/", ClientDocumentDownloadView.as_view(), name="v1-client-doc-download"),
    path("api/v1/clients/<uuid:client_id>/visits/history/", ClientVisitsHistoryView.as_view(), name="v1-client-history"),

    # Legacy Aliases (TZ_CRM_SERVICES_SPHERE Section 5)
    path("api/barbershop/clients/", ClientListCreateView.as_view(), name="legacy-clients"),
    path("api/barbershop/clients/<uuid:client_id>/", ClientDetailView.as_view(), name="legacy-client-detail"),
    path("api/barbershop/clients/<uuid:client_id>/documents/", ClientDocumentsView.as_view(), name="legacy-client-docs"),
    path("api/barbershop/clients/<uuid:client_id>/documents/<uuid:doc_id>/", ClientDocumentDetailView.as_view(), name="legacy-client-doc-detail"),
    path("api/barbershop/clients/<uuid:client_id>/visits/history/", ClientVisitsHistoryView.as_view(), name="legacy-client-history"),

    # Internal API
    path("internal/v1/clients/find-or-create/", InternalFindOrCreateClientView.as_view(), name="internal-find-or-create-client"),
    path("internal/v1/clients/<uuid:client_id>/", InternalClientDetailView.as_view(), name="internal-client-detail"),
]
