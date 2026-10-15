from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from django.http import HttpResponse, FileResponse
import uuid
import os
from datetime import date

from libs.common.auth import verify_token
from libs.common.exceptions import UnauthorizedError, ForbiddenError, CRMException, NotFoundError
from libs.common.response import error_response
from libs.common.pagination import PaginationParams, paginate_results
from backend.services.client.application.dto import CreateClientDTO, UpdateClientDTO
from backend.services.client.application.use_cases import (
    CreateClientUseCase,
    FindOrCreateClientUseCase,
    UpdateClientUseCase,
    UploadDocumentUseCase,
)
from backend.services.client.infrastructure.uow import DjangoClientUnitOfWork
from backend.services.client.infrastructure.repositories import DjangoClientRepository, DjangoClientDocumentRepository
from backend.services.client.infrastructure.storage import LocalDiskFileStorage


def get_current_user_from_request(request):
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise UnauthorizedError("Missing or invalid Authorization header")
    token = auth_header.split(" ")[1]
    return verify_token(token)


class ClientListCreateView(APIView):
    def get(self, request):
        try:
            user = get_current_user_from_request(request)
            search = request.query_params.get("search")
            repo = DjangoClientRepository()
            clients = repo.list_by_company(uuid.UUID(user.company_id), search=search)

            params = PaginationParams.from_request_params(
                request.query_params.get("limit"), request.query_params.get("offset")
            )
            total = len(clients)
            paginated = clients[params.offset : params.offset + params.limit]

            results = [
                {
                    "id": str(c.id),
                    "full_name": c.full_name,
                    "phone": str(c.phone),
                    "birth_date": str(c.birth_date) if c.birth_date else None,
                    "status": c.status,
                    "notes": c.notes,
                    "version": c.version,
                    "created_at": c.created_at.isoformat(),
                }
                for c in paginated
            ]
            return Response(paginate_results(results, total, params))
        except CRMException as e:
            return Response(error_response(e.code, e.message), status=e.status_code)

    def post(self, request):
        try:
            user = get_current_user_from_request(request)
            data = request.data
            bdate = date.fromisoformat(data["birth_date"]) if data.get("birth_date") else None
            dto = CreateClientDTO(
                company_id=uuid.UUID(user.company_id),
                full_name=data["full_name"],
                phone=data["phone"],
                birth_date=bdate,
                status=data.get("status", "active"),
                notes=data.get("notes"),
            )
            uow = DjangoClientUnitOfWork()
            res = CreateClientUseCase(uow).execute(dto)
            return Response({
                "id": res.id,
                "full_name": res.full_name,
                "phone": res.phone,
                "birth_date": res.birth_date,
                "status": res.status,
                "notes": res.notes,
                "version": res.version,
            }, status=201)
        except CRMException as e:
            return Response(error_response(e.code, e.message, e.details), status=e.status_code)


class ClientDetailView(APIView):
    def get(self, request, client_id):
        try:
            user = get_current_user_from_request(request)
            repo = DjangoClientRepository()
            c = repo.get_by_id(uuid.UUID(user.company_id), uuid.UUID(str(client_id)))
            if not c:
                return Response(error_response("not_found", "Client not found"), status=404)
            return Response({
                "id": str(c.id),
                "full_name": c.full_name,
                "phone": str(c.phone),
                "birth_date": str(c.birth_date) if c.birth_date else None,
                "status": c.status,
                "notes": c.notes,
                "version": c.version,
                "created_at": c.created_at.isoformat(),
            })
        except CRMException as e:
            return Response(error_response(e.code, e.message), status=e.status_code)

    def patch(self, request, client_id):
        try:
            user = get_current_user_from_request(request)
            data = request.data
            if_match = request.headers.get("If-Match")
            expected_ver = int(if_match) if if_match and if_match.isdigit() else data.get("expected_version")

            bdate = date.fromisoformat(data["birth_date"]) if data.get("birth_date") else None
            dto = UpdateClientDTO(
                full_name=data.get("full_name"),
                phone=data.get("phone"),
                birth_date=bdate,
                status=data.get("status"),
                notes=data.get("notes"),
                expected_version=expected_ver,
            )
            uow = DjangoClientUnitOfWork()
            res = UpdateClientUseCase(uow).execute(uuid.UUID(user.company_id), uuid.UUID(str(client_id)), dto)
            return Response({
                "id": res.id,
                "full_name": res.full_name,
                "phone": res.phone,
                "status": res.status,
                "version": res.version,
            })
        except CRMException as e:
            return Response(error_response(e.code, e.message, e.details), status=e.status_code)

    def delete(self, request, client_id):
        try:
            user = get_current_user_from_request(request)
            repo = DjangoClientRepository()
            repo.delete(uuid.UUID(user.company_id), uuid.UUID(str(client_id)))
            return Response(status=204)
        except CRMException as e:
            return Response(error_response(e.code, e.message), status=e.status_code)


class ClientDocumentsView(APIView):
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get(self, request, client_id):
        try:
            user = get_current_user_from_request(request)
            repo = DjangoClientDocumentRepository()
            docs = repo.list_by_client(uuid.UUID(user.company_id), uuid.UUID(str(client_id)))
            return Response([
                {
                    "id": str(d.id),
                    "file_name": d.file_name,
                    "file_size": d.file_size,
                    "file_comment": d.file_comment,
                    "created_at": d.created_at.isoformat(),
                    "download_url": f"/api/v1/clients/{client_id}/documents/{d.id}/download/",
                }
                for d in docs
            ])
        except CRMException as e:
            return Response(error_response(e.code, e.message), status=e.status_code)

    def post(self, request, client_id):
        try:
            user = get_current_user_from_request(request)
            uploaded_file = request.FILES.get("file")
            if not uploaded_file:
                return Response(error_response("validation_error", "No file provided in form-data"), status=400)

            content = uploaded_file.read()
            comment = request.data.get("file_comment") or request.data.get("comment")

            uow = DjangoClientUnitOfWork()
            storage = LocalDiskFileStorage()
            use_case = UploadDocumentUseCase(uow, storage)
            doc_dto = use_case.execute(
                company_id=uuid.UUID(user.company_id),
                client_id=uuid.UUID(str(client_id)),
                file_name=uploaded_file.name,
                content=content,
                file_comment=comment,
            )
            return Response({
                "id": doc_dto.id,
                "file_name": doc_dto.file_name,
                "file_size": doc_dto.file_size,
                "file_comment": doc_dto.file_comment,
                "created_at": doc_dto.created_at,
            }, status=201)
        except CRMException as e:
            return Response(error_response(e.code, e.message, e.details), status=e.status_code)


class ClientDocumentDetailView(APIView):
    def delete(self, request, client_id, doc_id):
        try:
            user = get_current_user_from_request(request)
            repo = DjangoClientDocumentRepository()
            repo.delete(uuid.UUID(user.company_id), uuid.UUID(str(doc_id)))
            return Response(status=204)
        except CRMException as e:
            return Response(error_response(e.code, e.message), status=e.status_code)


class ClientDocumentDownloadView(APIView):
    def get(self, request, client_id, doc_id):
        try:
            user = get_current_user_from_request(request)
            repo = DjangoClientDocumentRepository()
            doc = repo.get_by_id(uuid.UUID(user.company_id), uuid.UUID(str(doc_id)))
            if not doc:
                return Response(error_response("not_found", "Document not found"), status=404)

            # Check if Nginx X-Accel-Redirect is supported, or serve directly
            if os.getenv("USE_X_ACCEL", "False").lower() == "true":
                response = HttpResponse()
                response["X-Accel-Redirect"] = f"/protected-media/{user.company_id}/{client_id}/{doc.id}"
                response["Content-Disposition"] = f'attachment; filename="{doc.file_name}"'
                return response
            elif os.path.exists(doc.file_path):
                return FileResponse(open(doc.file_path, "rb"), as_attachment=True, filename=doc.file_name)
            else:
                return Response(error_response("not_found", "File not found on disk"), status=404)
        except CRMException as e:
            return Response(error_response(e.code, e.message), status=e.status_code)


class ClientVisitsHistoryView(APIView):
    def get(self, request, client_id):
        try:
            user = get_current_user_from_request(request)
            repo = DjangoClientRepository()
            c = repo.get_by_id(uuid.UUID(user.company_id), uuid.UUID(str(client_id)))
            if not c:
                return Response(error_response("not_found", "Client not found"), status=404)

            # Returns visits history structure matching TZ
            return Response({
                "client_id": str(c.id),
                "client_name": c.full_name,
                "total_visits": 0,
                "total_spent": "0.00",
                "visits": [],
            })
        except CRMException as e:
            return Response(error_response(e.code, e.message), status=e.status_code)


# Internal API views
class InternalFindOrCreateClientView(APIView):
    def post(self, request):
        try:
            company_id = request.data.get("company_id")
            name = request.data.get("full_name") or request.data.get("client_name")
            phone = request.data.get("phone") or request.data.get("client_phone")

            if not company_id or not name or not phone:
                return Response(error_response("validation_error", "company_id, full_name, and phone are required"), status=400)

            uow = DjangoClientUnitOfWork()
            dto = FindOrCreateClientUseCase(uow).execute(uuid.UUID(str(company_id)), name, phone)
            return Response({
                "id": dto.id,
                "company_id": dto.company_id,
                "full_name": dto.full_name,
                "phone": dto.phone,
                "status": dto.status,
            })
        except CRMException as e:
            return Response(error_response(e.code, e.message, e.details), status=e.status_code)


class InternalClientDetailView(APIView):
    def get(self, request, client_id):
        company_id = request.query_params.get("company_id")
        if not company_id:
            return Response(error_response("validation_error", "company_id is required"), status=400)

        repo = DjangoClientRepository()
        c = repo.get_by_id(uuid.UUID(company_id), uuid.UUID(str(client_id)))
        if not c:
            return Response(error_response("not_found", "Client not found"), status=404)

        return Response({
            "id": str(c.id),
            "full_name": c.full_name,
            "phone": str(c.phone),
            "status": c.status,
        })
