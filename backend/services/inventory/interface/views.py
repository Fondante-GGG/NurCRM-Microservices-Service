from decimal import Decimal, InvalidOperation
import uuid

from rest_framework.response import Response
from rest_framework.views import APIView

from backend.services.inventory.application.use_cases import (
    CommitReservationUseCase,
    ReleaseReservationUseCase,
    ReserveStockUseCase,
)
from backend.services.inventory.infrastructure.repositories import DjangoInventoryRepository
from libs.common.auth import verify_internal_service_request, verify_token
from libs.common.exceptions import CRMException, UnauthorizedError, ValidationError
from libs.common.response import error_response


def _current_user(request):
    authorization = request.headers.get("Authorization", "")
    if not authorization.startswith("Bearer "):
        raise UnauthorizedError("Missing or invalid Authorization header")
    return verify_token(authorization.split(" ", 1)[1])


def _stock_response(balance):
    return {
        "id": str(balance.id),
        "product_id": str(balance.product_id),
        "variant_id": str(balance.variant_id) if balance.variant_id else None,
        "branch_id": str(balance.branch_id) if balance.branch_id else None,
        "location_code": balance.location_code,
        "quantity": str(balance.quantity),
        "reserved": str(balance.reserved),
        "available": str(balance.available),
    }


def _decimal(value, field_name):
    try:
        result = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        raise ValidationError(f"{field_name} must be a decimal number")
    if not result.is_finite():
        raise ValidationError(f"{field_name} must be finite")
    return result


class StockListView(APIView):
    def get(self, request):
        try:
            user = _current_user(request)
            product_id = uuid.UUID(request.query_params["product_id"]) if request.query_params.get("product_id") else None
            branch_id = uuid.UUID(request.query_params["branch_id"]) if request.query_params.get("branch_id") else None
            balances = DjangoInventoryRepository().list_stock(
                uuid.UUID(user.company_id), product_id=product_id, branch_id=branch_id
            )
            return Response([_stock_response(balance) for balance in balances])
        except CRMException as exc:
            return Response(error_response(exc.code, exc.message, exc.details), status=exc.status_code)
        except (ValueError, TypeError):
            return Response(error_response("validation_error", "Invalid stock filter"), status=400)


class StockMovementCreateView(APIView):
    def post(self, request):
        try:
            user = _current_user(request)
            if user.role not in ("owner", "admin", "support"):
                return Response(error_response("forbidden", "Inventory adjustment permission required"), status=403)
            data = request.data
            if not isinstance(data, dict):
                raise ValidationError("A stock movement object is required")
            movement_type = str(data.get("movement_type", ""))
            if movement_type not in ("receipt", "return", "write_off"):
                raise ValidationError("movement_type must be receipt, return, or write_off")
            location_code = str(data.get("location_code", "default")).strip()
            if not location_code or len(location_code) > 64:
                raise ValidationError("location_code must contain 1 to 64 characters")

            balance = DjangoInventoryRepository().adjust_stock(
                company_id=uuid.UUID(user.company_id),
                product_id=uuid.UUID(str(data.get("product_id", ""))),
                variant_id=uuid.UUID(str(data["variant_id"])) if data.get("variant_id") else None,
                branch_id=uuid.UUID(str(data["branch_id"])) if data.get("branch_id") else None,
                location_code=location_code,
                quantity=_decimal(data.get("quantity"), "quantity"),
                movement_type=movement_type,
                source_key=str(request.headers.get("Idempotency-Key", data.get("source_key", ""))).strip(),
                reason=str(data.get("reason", "")),
            )
            return Response(_stock_response(balance), status=201)
        except CRMException as exc:
            return Response(error_response(exc.code, exc.message, exc.details), status=exc.status_code)
        except (ValueError, TypeError):
            return Response(error_response("validation_error", "Invalid stock movement"), status=400)


class InternalReservationView(APIView):
    def post(self, request):
        try:
            verify_internal_service_request(request, "inventory-service")
            data = request.data
            if not isinstance(data, dict):
                raise ValidationError("A reservation object is required")
            company_id = uuid.UUID(str(data.get("company_id", "")))
            idempotency_key = str(
                request.headers.get("Idempotency-Key", data.get("idempotency_key", ""))
            ).strip()
            reservation_id = ReserveStockUseCase(DjangoInventoryRepository()).execute(
                company_id,
                idempotency_key,
                data.get("items"),
            )
            return Response({"id": str(reservation_id), "status": "reserved"}, status=201)
        except CRMException as exc:
            return Response(error_response(exc.code, exc.message, exc.details), status=exc.status_code)
        except (ValueError, TypeError):
            return Response(error_response("validation_error", "Invalid reservation"), status=400)


class InternalReservationActionView(APIView):
    def post(self, request, reservation_id, action):
        try:
            verify_internal_service_request(request, "inventory-service")
            data = request.data if isinstance(request.data, dict) else {}
            company_id = uuid.UUID(str(data.get("company_id", "")))
            if action == "commit":
                CommitReservationUseCase(DjangoInventoryRepository()).execute(company_id, reservation_id)
                return Response({"id": str(reservation_id), "status": "committed"})
            if action == "release":
                ReleaseReservationUseCase(DjangoInventoryRepository()).execute(company_id, reservation_id)
                return Response({"id": str(reservation_id), "status": "released"})
            raise ValidationError("action must be commit or release")
        except CRMException as exc:
            return Response(error_response(exc.code, exc.message, exc.details), status=exc.status_code)
        except (ValueError, TypeError):
            return Response(error_response("validation_error", "Invalid reservation identifier"), status=400)
