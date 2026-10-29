from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
import uuid
from decimal import Decimal, InvalidOperation
from django.db import IntegrityError

from libs.common.auth import verify_token, verify_internal_service_request
from libs.common.exceptions import (
    ConflictError,
    CRMException,
    NotFoundError,
    UnauthorizedError,
    ValidationError as CRMValidationError,
)
from libs.common.response import error_response
from libs.common.pagination import PaginationParams, paginate_results
from backend.services.catalog.application.dto import CreateServiceDTO, UpdateServiceDTO
from backend.services.catalog.application.use_cases import (
    CreateCategoryUseCase,
    CreateProductUseCase,
    CreateServiceUseCase,
    UpdateServiceUseCase,
    UpdateProductUseCase,
    SetSalaryRateUseCase,
)
from backend.services.catalog.infrastructure.uow import DjangoCatalogUnitOfWork
from backend.services.catalog.infrastructure.repositories import (
    DjangoServiceCategoryRepository,
    DjangoProductRepository,
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
            if user.role not in ("owner", "admin", "support"):
                return Response(error_response("forbidden", "Only owner, admin, or support can create categories"), status=403)
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
            if user.role not in ("owner", "admin", "support"):
                return Response(error_response("forbidden", "Only owner, admin, or support can delete categories"), status=403)
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
            if user.role not in ("owner", "admin", "support"):
                return Response(error_response("forbidden", "Only owner, admin, or support can create services"), status=403)
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
            if user.role not in ("owner", "admin", "support"):
                return Response(error_response("forbidden", "Only owner, admin, or support can update services"), status=403)
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
            if user.role not in ("owner", "admin", "support"):
                return Response(error_response("forbidden", "Only owner, admin, or support can delete services"), status=403)
            repo = DjangoServiceRepository()
            repo.delete(uuid.UUID(user.company_id), uuid.UUID(str(service_id)))
            return Response(status=204)
        except CRMException as e:
            return Response(error_response(e.code, e.message), status=e.status_code)


class SalaryRatesView(APIView):
    def get(self, request):
        try:
            user = get_current_user_from_request(request)
            if not user.has_perm("can_view_salary") and user.role not in ("owner", "admin", "support"):
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
            if user.role not in ("owner", "admin", "support"):
                return Response(error_response("forbidden", "Only owner, admin, or support can set salary rates"), status=403)

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
class InternalCategoriesView(APIView):
    def get(self, request):
        try:
            verify_internal_service_request(request, "catalog-service")
            company_id = request.query_params.get("company_id")
            if not company_id:
                return Response(error_response("validation_error", "company_id is required"), status=400)

            repo = DjangoServiceCategoryRepository()
            categories = repo.list_by_company(uuid.UUID(company_id))
            return Response([
                {
                    "id": str(c.id),
                    "name": c.name,
                    "is_active": c.is_active,
                }
                for c in categories if c.is_active
            ])
        except CRMException as e:
            return Response(error_response(e.code, e.message, e.details), status=e.status_code)


class InternalServicesView(APIView):
    def get(self, request):
        try:
            verify_internal_service_request(request, "catalog-service")
            company_id = request.query_params.get("company_id")
            service_ids_str = request.query_params.get("service_ids", "")
            if not company_id:
                return Response(error_response("validation_error", "company_id is required"), status=400)

            repo = DjangoServiceRepository()
            if service_ids_str:
                service_ids = [uuid.UUID(s.strip()) for s in service_ids_str.split(",") if s.strip()]
                services = repo.list_by_ids(uuid.UUID(company_id), service_ids)
            else:
                services = [s for s in repo.list_by_company(uuid.UUID(company_id)) if s.is_active]

            return Response([
                {
                    "id": str(s.id),
                    "category_id": str(s.category_id),
                    "name": s.name,
                    "price": str(s.price.amount),
                    "time": s.time_minutes,
                    "time_minutes": s.time_minutes,
                    "barbers": [str(b) for b in s.barbers],
                    "is_active": s.is_active,
                }
                for s in services
            ])
        except CRMException as e:
            return Response(error_response(e.code, e.message, e.details), status=e.status_code)


class InternalRateView(APIView):
    def get(self, request, service_id):
        try:
            verify_internal_service_request(request, "catalog-service")
            company_id = request.query_params.get("company_id")
            master_id = request.query_params.get("master_id")
            if not company_id:
                return Response(error_response("validation_error", "company_id is required"), status=400)

            master_uuid = uuid.UUID(master_id) if master_id else None
            repo = DjangoSalaryRateRepository()
            rate = repo.get_rate(uuid.UUID(company_id), uuid.UUID(str(service_id)), master_uuid)
            percent = float(rate.percent) if rate else 0.0
            return Response({"percent": percent})
        except CRMException as e:
            return Response(error_response(e.code, e.message, e.details), status=e.status_code)


def _product_response(product, include_cost: bool = False):
    result = {
        "id": str(product.id),
        "name": product.name,
        "sku": product.sku,
        "category": product.category,
        "price": str(product.price.amount),
        "wholesale_price": str(product.wholesale_price.amount) if product.wholesale_price else None,
        "unit_code": product.unit_code,
        "minimum_quantity": str(product.minimum_quantity),
        "quantity_step": str(product.quantity_step),
        "attributes": product.attributes,
        "is_active": product.is_active,
        "version": product.version,
    }
    if include_cost:
        result["cost_price"] = str(product.cost_price.amount)
    return result


def _decimal_value(data, field_name: str, default=None):
    value = data.get(field_name, default)
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        raise CRMValidationError(f"{field_name} must be a decimal number")


class ProductListCreateView(APIView):
    def get(self, request):
        try:
            user = get_current_user_from_request(request)
            products = DjangoProductRepository().list_by_company(
                uuid.UUID(user.company_id),
                active_only=request.query_params.get("active_only", "").lower() == "true",
            )
            params = PaginationParams.from_request_params(
                request.query_params.get("limit"), request.query_params.get("offset")
            )
            page = products[params.offset : params.offset + params.limit]
            include_cost = user.role in ("owner", "admin", "support")
            return Response(paginate_results(
                [_product_response(product, include_cost=include_cost) for product in page],
                len(products),
                params,
            ))
        except CRMException as e:
            return Response(error_response(e.code, e.message, e.details), status=e.status_code)
        except (ValueError, TypeError):
            return Response(error_response("validation_error", "Invalid company identifier"), status=400)

    def post(self, request):
        try:
            user = get_current_user_from_request(request)
            if user.role not in ("owner", "admin", "support"):
                return Response(error_response("forbidden", "Only owner, admin, or support can create products"), status=403)
            data = request.data
            if not isinstance(data, dict):
                raise CRMValidationError("A product object is required")
            attributes = data.get("attributes", {})
            if not isinstance(attributes, dict):
                raise CRMValidationError("attributes must be an object")

            product = CreateProductUseCase(DjangoProductRepository()).execute(
                company_id=uuid.UUID(user.company_id),
                name=str(data.get("name", "")),
                sku=str(data.get("sku", "")),
                category=str(data.get("category", "")),
                price=_decimal_value(data, "price", "0"),
                cost_price=_decimal_value(data, "cost_price", "0"),
                wholesale_price=_decimal_value(data, "wholesale_price"),
                unit_code=str(data.get("unit_code", "pcs")),
                minimum_quantity=_decimal_value(data, "minimum_quantity", "1"),
                quantity_step=_decimal_value(data, "quantity_step", "1"),
                attributes=attributes,
                is_active=data.get("is_active", True),
            )
            return Response(_product_response(product, include_cost=True), status=status.HTTP_201_CREATED)
        except IntegrityError:
            error = ConflictError("SKU already exists for this company", code="duplicate_sku")
            return Response(error_response(error.code, error.message), status=error.status_code)
        except CRMException as e:
            return Response(error_response(e.code, e.message, e.details), status=e.status_code)
        except (ValueError, TypeError):
            return Response(error_response("validation_error", "Invalid product data"), status=400)


class ProductDetailView(APIView):
    def get(self, request, product_id):
        try:
            user = get_current_user_from_request(request)
            product = DjangoProductRepository().get_by_id(
                uuid.UUID(user.company_id), uuid.UUID(str(product_id))
            )
            if product is None:
                raise NotFoundError(f"Product {product_id} not found")
            return Response(_product_response(
                product,
                include_cost=user.role in ("owner", "admin", "support"),
            ))
        except CRMException as e:
            return Response(error_response(e.code, e.message, e.details), status=e.status_code)
        except (ValueError, TypeError):
            return Response(error_response("validation_error", "Invalid product identifier"), status=400)

    def patch(self, request, product_id):
        try:
            user = get_current_user_from_request(request)
            if user.role not in ("owner", "admin", "support"):
                return Response(error_response("forbidden", "Only owner, admin, or support can update products"), status=403)
            data = request.data
            if not isinstance(data, dict):
                raise CRMValidationError("A product object is required")
            if "attributes" in data and not isinstance(data["attributes"], dict):
                raise CRMValidationError("attributes must be an object")
            values = {
                field_name: data[field_name]
                for field_name in ("name", "sku", "category", "unit_code", "attributes", "is_active")
                if field_name in data
            }
            for field_name in ("price", "cost_price", "wholesale_price", "minimum_quantity", "quantity_step"):
                if field_name in data:
                    values[field_name] = _decimal_value(data, field_name)
            if values.get("wholesale_price", object()) is None:
                values["wholesale_price"] = None

            if_match = request.headers.get("If-Match")
            expected_version = int(if_match) if if_match and if_match.isdigit() else data.get("expected_version")
            product = UpdateProductUseCase(DjangoProductRepository()).execute(
                uuid.UUID(user.company_id),
                uuid.UUID(str(product_id)),
                expected_version=expected_version,
                values=values,
            )
            return Response(_product_response(product, include_cost=True))
        except IntegrityError:
            error = ConflictError("SKU already exists for this company", code="duplicate_sku")
            return Response(error_response(error.code, error.message), status=error.status_code)
        except CRMException as e:
            return Response(error_response(e.code, e.message, e.details), status=e.status_code)
        except (ValueError, TypeError):
            return Response(error_response("validation_error", "Invalid product data"), status=400)


class InternalProductsView(APIView):
    def get(self, request):
        try:
            verify_internal_service_request(request, "catalog-service")
            company_id = uuid.UUID(request.query_params.get("company_id", ""))
            product_ids = [
                uuid.UUID(value.strip())
                for value in request.query_params.get("product_ids", "").split(",")
                if value.strip()
            ]
            if not product_ids or len(product_ids) > 200:
                raise CRMValidationError("product_ids must contain between 1 and 200 identifiers")
            products = DjangoProductRepository().list_by_ids(company_id, product_ids)
            return Response([_product_response(product) for product in products])
        except CRMException as e:
            return Response(error_response(e.code, e.message, e.details), status=e.status_code)
        except (ValueError, TypeError):
            return Response(error_response("validation_error", "Invalid company or product identifier"), status=400)
