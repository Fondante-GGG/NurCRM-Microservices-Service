from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
import uuid
from decimal import Decimal

from libs.common.auth import verify_token
from libs.common.exceptions import UnauthorizedError, ForbiddenError, CRMException, NotFoundError
from libs.common.response import error_response
from libs.common.pagination import PaginationParams, paginate_results
from backend.services.catalog.application.dto import CreateServiceDTO, UpdateServiceDTO
from backend.services.catalog.application.use_cases import (
    CreateCategoryUseCase,
    CreateServiceUseCase,
    UpdateServiceUseCase,
    SetSalaryRateUseCase,
)
from backend.services.catalog.infrastructure.uow import DjangoCatalogUnitOfWork
from backend.services.catalog.infrastructure.repositories import (
    DjangoServiceCategoryRepository,
    DjangoServiceRepository,
    DjangoSalaryRateRepository,
)


def get_current_user_from_request(request):
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise UnauthorizedError("Missing or invalid Authorization header")
    token = auth_header.split(" ")[1]
    return verify_token(token)


class CategoryListCreateView(APIView):
    def get(self, request):
        try:
            user = get_current_user_from_request(request)
            repo = DjangoServiceCategoryRepository()
            categories = repo.list_by_company(uuid.UUID(user.company_id))
            results = [
                {
                    "id": str(c.id),
                    "name": c.name,
                    "is_active": c.is_active,
                    "version": c.version,
                }
                for c in categories
            ]
            return Response(results)
        except CRMException as e:
            return Response(error_response(e.code, e.message), status=e.status_code)

    def post(self, request):
        try:
            user = get_current_user_from_request(request)
            name = request.data.get("name")
            if not name:
                return Response(error_response("validation_error", "Category name is required"), status=400)
            uow = DjangoCatalogUnitOfWork()
            dto = CreateCategoryUseCase(uow).execute(
                company_id=uuid.UUID(user.company_id),
                name=name,
                is_active=request.data.get("is_active", True),
            )
            return Response({"id": dto.id, "name": dto.name, "is_active": dto.is_active}, status=201)
        except CRMException as e:
            return Response(error_response(e.code, e.message, e.details), status=e.status_code)


class CategoryDetailView(APIView):
    def delete(self, request, category_id):
        try:
            user = get_current_user_from_request(request)
            repo = DjangoServiceCategoryRepository()
            repo.delete(uuid.UUID(user.company_id), uuid.UUID(str(category_id)))
            return Response(status=204)
        except CRMException as e:
            return Response(error_response(e.code, e.message), status=e.status_code)


class ServiceListCreateView(APIView):
    def get(self, request):
        try:
            user = get_current_user_from_request(request)
            category_id = request.query_params.get("category_id")
            cat_uuid = uuid.UUID(category_id) if category_id else None
            repo = DjangoServiceRepository()
            services = repo.list_by_company(uuid.UUID(user.company_id), category_id=cat_uuid)

            params = PaginationParams.from_request_params(
                request.query_params.get("limit"), request.query_params.get("offset")
            )
            total = len(services)
            paginated = services[params.offset : params.offset + params.limit]

            results = [
                {
                    "id": str(s.id),
                    "category_id": str(s.category_id),
                    "name": s.name,
                    "price": str(s.price.amount),
                    "time": s.time_minutes,
                    "time_minutes": s.time_minutes,
                    "barbers": [str(b) for b in s.barbers],
                    "is_active": s.is_active,
                    "version": s.version,
                }
                for s in paginated
            ]
            return Response(paginate_results(results, total, params))
        except CRMException as e:
            return Response(error_response(e.code, e.message), status=e.status_code)

    def post(self, request):
        try:
            user = get_current_user_from_request(request)
            data = request.data
            barbers = [uuid.UUID(str(b)) for b in data.get("barbers", [])]
            dto = CreateServiceDTO(
                company_id=uuid.UUID(user.company_id),
                category_id=uuid.UUID(data["category_id"]),
                name=data["name"],
                price=Decimal(str(data.get("price", "0"))),
                time_minutes=int(data.get("time", data.get("time_minutes", 30))),
                barbers=barbers,
                is_active=data.get("is_active", True),
            )
            uow = DjangoCatalogUnitOfWork()
            res = CreateServiceUseCase(uow).execute(dto)
            return Response({
                "id": res.id,
                "category_id": res.category_id,
                "name": res.name,
                "price": str(res.price),
                "time": res.time_minutes,
                "time_minutes": res.time_minutes,
                "barbers": res.barbers,
                "is_active": res.is_active,
                "version": res.version,
            }, status=201)
        except CRMException as e:
            return Response(error_response(e.code, e.message, e.details), status=e.status_code)


class ServiceDetailView(APIView):
    def patch(self, request, service_id):
        try:
            user = get_current_user_from_request(request)
            data = request.data
            if_match = request.headers.get("If-Match")
            expected_ver = int(if_match) if if_match and if_match.isdigit() else data.get("expected_version")

            barbers = None
            if "barbers" in data:
                barbers = [uuid.UUID(str(b)) for b in data["barbers"]]

            dto = UpdateServiceDTO(
                name=data.get("name"),
                category_id=uuid.UUID(data["category_id"]) if "category_id" in data else None,
                price=Decimal(str(data["price"])) if "price" in data else None,
                time_minutes=int(data["time"]) if "time" in data else (int(data["time_minutes"]) if "time_minutes" in data else None),
                barbers=barbers,
                is_active=data.get("is_active"),
                expected_version=expected_ver,
            )
            uow = DjangoCatalogUnitOfWork()
            res = UpdateServiceUseCase(uow).execute(uuid.UUID(user.company_id), uuid.UUID(str(service_id)), dto)
            return Response({
                "id": res.id,
                "name": res.name,
                "price": str(res.price),
                "time": res.time_minutes,
                "is_active": res.is_active,
                "version": res.version,
            })
        except CRMException as e:
            return Response(error_response(e.code, e.message, e.details), status=e.status_code)

    def delete(self, request, service_id):
        try:
            user = get_current_user_from_request(request)
            repo = DjangoServiceRepository()
            repo.delete(uuid.UUID(user.company_id), uuid.UUID(str(service_id)))
            return Response(status=204)
        except CRMException as e:
            return Response(error_response(e.code, e.message), status=e.status_code)


class SalaryRatesView(APIView):
    def get(self, request):
        try:
            user = get_current_user_from_request(request)
            if not user.has_perm("can_view_salary"):
                return Response(error_response("forbidden", "Salary permission required"), status=403)

            repo = DjangoSalaryRateRepository()
            rates = repo.list_by_company(uuid.UUID(user.company_id))
            return Response([
                {
                    "id": str(r.id),
                    "service_id": str(r.service_id),
                    "master_id": str(r.master_id) if r.master_id else None,
                    "percent": float(r.percent),
                }
                for r in rates
            ])
        except CRMException as e:
            return Response(error_response(e.code, e.message), status=e.status_code)

    def put(self, request, service_id):
        try:
            user = get_current_user_from_request(request)
            if not user.has_perm("can_view_salary"):
                return Response(error_response("forbidden", "Salary permission required"), status=403)

            percent = Decimal(str(request.data.get("percent", "0")))
            master_id = request.data.get("master_id")
            master_uuid = uuid.UUID(str(master_id)) if master_id else None

            uow = DjangoCatalogUnitOfWork()
            res = SetSalaryRateUseCase(uow).execute(
                company_id=uuid.UUID(user.company_id),
                service_id=uuid.UUID(str(service_id)),
                percent=percent,
                master_id=master_uuid,
            )
            return Response({
                "id": res.id,
                "service_id": res.service_id,
                "master_id": res.master_id,
                "percent": float(res.percent),
            })
        except CRMException as e:
            return Response(error_response(e.code, e.message, e.details), status=e.status_code)


# Internal API views
class InternalServicesView(APIView):
    def get(self, request):
        company_id = request.query_params.get("company_id")
        service_ids_str = request.query_params.get("service_ids", "")
        if not company_id:
            return Response(error_response("validation_error", "company_id is required"), status=400)

        service_ids = [uuid.UUID(s.strip()) for s in service_ids_str.split(",") if s.strip()]
        repo = DjangoServiceRepository()
        services = repo.list_by_ids(uuid.UUID(company_id), service_ids)
        return Response([
            {
                "id": str(s.id),
                "name": s.name,
                "price": str(s.price.amount),
                "time_minutes": s.time_minutes,
                "barbers": [str(b) for b in s.barbers],
                "is_active": s.is_active,
            }
            for s in services
        ])


class InternalRateView(APIView):
    def get(self, request, service_id):
        company_id = request.query_params.get("company_id")
        master_id = request.query_params.get("master_id")
        if not company_id:
            return Response(error_response("validation_error", "company_id is required"), status=400)

        master_uuid = uuid.UUID(master_id) if master_id else None
        repo = DjangoSalaryRateRepository()
        rate = repo.get_rate(uuid.UUID(company_id), uuid.UUID(str(service_id)), master_uuid)
        percent = float(rate.percent) if rate else 0.0
        return Response({"percent": percent})
