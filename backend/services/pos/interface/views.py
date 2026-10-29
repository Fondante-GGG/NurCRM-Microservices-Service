import uuid

from rest_framework.response import Response
from rest_framework.views import APIView

from backend.services.pos.application.use_cases import CheckoutUseCase
from backend.services.pos.infrastructure.clients import HttpCatalogClient, HttpInventoryClient
from backend.services.pos.infrastructure.repositories import DjangoSaleRepository
from libs.common.auth import verify_token
from libs.common.exceptions import CRMException, UnauthorizedError, ValidationError
from libs.common.pagination import PaginationParams, paginate_results
from libs.common.response import error_response


def _current_user(request):
    authorization = request.headers.get("Authorization", "")
    if not authorization.startswith("Bearer "):
        raise UnauthorizedError("Missing or invalid Authorization header")
    return verify_token(authorization.split(" ", 1)[1])


def _require_pos_access(user):
    if user.role in ("owner", "admin", "support", "cashier"):
        return
    if user.has_perm("can_view_cashbox"):
        return
    raise CRMException("POS permission required", code="forbidden", status_code=403)


def _sale_response(sale):
    return {
        "id": str(sale.id),
        "cashier_id": str(sale.cashier_id),
        "status": sale.status,
        "payment_method": sale.payment_method,
        "source": sale.source,
        "device_id": sale.device_id,
        "discount": str(sale.discount.amount),
        "total": str(sale.total.amount),
        "inventory_reservation_id": (
            str(sale.inventory_reservation_id) if sale.inventory_reservation_id else None
        ),
        "items": [
            {
                "product_id": str(line.product_id),
                "variant_id": str(line.variant_id) if line.variant_id else None,
                "branch_id": str(line.branch_id) if line.branch_id else None,
                "location_code": line.location_code,
                "name": line.name,
                "sku": line.sku,
                "quantity": str(line.quantity),
                "unit_code": line.unit_code,
                "unit_price": str(line.unit_price.amount),
                "discount": str(line.discount.amount),
                "total": str(line.total.amount),
            }
            for line in sale.items
        ],
    }


class SaleListCreateView(APIView):
    def get(self, request):
        try:
            user = _current_user(request)
            _require_pos_access(user)
            sales = DjangoSaleRepository().list_by_company(uuid.UUID(user.company_id))
            params = PaginationParams.from_request_params(
                request.query_params.get("limit"), request.query_params.get("offset")
            )
            page = sales[params.offset : params.offset + params.limit]
            return Response(paginate_results([_sale_response(sale) for sale in page], len(sales), params))
        except CRMException as exc:
            return Response(error_response(exc.code, exc.message, exc.details), status=exc.status_code)
        except (ValueError, TypeError):
            return Response(error_response("validation_error", "Invalid user identity"), status=400)

    def post(self, request):
        try:
            user = _current_user(request)
            _require_pos_access(user)
            payload = request.data
            if not isinstance(payload, dict):
                raise ValidationError("A checkout object is required")
            idempotency_key = str(
                request.headers.get("Idempotency-Key", payload.get("idempotency_key", ""))
            ).strip()
            use_case = CheckoutUseCase(
                repository=DjangoSaleRepository(),
                catalog=HttpCatalogClient(),
                inventory=HttpInventoryClient(),
            )
            sale, created = use_case.execute(
                company_id=uuid.UUID(user.company_id),
                cashier_id=uuid.UUID(user.user_id),
                idempotency_key=idempotency_key,
                payload=payload,
            )
            return Response(_sale_response(sale), status=201 if created else 200)
        except CRMException as exc:
            return Response(error_response(exc.code, exc.message, exc.details), status=exc.status_code)
        except (ValueError, TypeError):
            return Response(error_response("validation_error", "Invalid checkout data"), status=400)


class SaleDetailView(APIView):
    def get(self, request, sale_id):
        try:
            user = _current_user(request)
            _require_pos_access(user)
            sale = DjangoSaleRepository().get_by_id(
                uuid.UUID(user.company_id), uuid.UUID(str(sale_id))
            )
            if sale is None:
                return Response(error_response("not_found", "Sale not found"), status=404)
            return Response(_sale_response(sale))
        except CRMException as exc:
            return Response(error_response(exc.code, exc.message, exc.details), status=exc.status_code)
        except (ValueError, TypeError):
            return Response(error_response("validation_error", "Invalid sale identifier"), status=400)
