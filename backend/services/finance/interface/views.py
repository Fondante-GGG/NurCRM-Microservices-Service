from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
import uuid
from decimal import Decimal
from datetime import date

from libs.common.auth import verify_token, verify_internal_service_request
from libs.common.exceptions import UnauthorizedError, ForbiddenError, CRMException, NotFoundError
from libs.common.response import error_response
from libs.common.pagination import PaginationParams, paginate_results
from backend.services.finance.domain.models import Material
from backend.services.finance.application.use_cases import (
    ProcessAppointmentCompletedUseCase,
    RegisterPayoutUseCase,
    GetSalarySummaryUseCase,
    OpenShiftUseCase,
    CloseShiftUseCase,
)
from backend.services.finance.infrastructure.uow import DjangoFinanceUnitOfWork
from backend.services.finance.infrastructure.repositories import (
    DjangoAccrualRepository,
    DjangoSalaryPayoutRepository,
    DjangoCashShiftRepository,
    DjangoWarehouseRepository,
)
from backend.services.finance.infrastructure.catalog_client import HttpCatalogClient


def get_current_user_from_request(request):
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise UnauthorizedError("Missing or invalid Authorization header")
    token = auth_header.split(" ")[1]
    return verify_token(token)


class ShiftListCreateView(APIView):
    def get(self, request):
        try:
            user = get_current_user_from_request(request)
            if not user.has_perm("can_view_cashbox") and user.role not in ("owner", "admin", "support"):
                return Response(error_response("forbidden", "Cashbox permission required"), status=403)

            repo = DjangoCashShiftRepository()
            shifts = repo.list_by_company(uuid.UUID(user.company_id))

            results = [
                {
                    "id": str(s.id),
                    "user_id": str(s.user_id),
                    "cashbox": s.cashbox,
                    "opening_cash": str(s.opening_cash.amount),
                    "closing_cash": str(s.closing_cash.amount) if s.closing_cash else None,
                    "sales_total": str(s.sales_total.amount),
                    "sales_count": s.sales_count,
                    "status": s.status,
                    "opened_at": s.opened_at.isoformat(),
                    "closed_at": s.closed_at.isoformat() if s.closed_at else None,
                }
                for s in shifts
            ]
            return Response(results)
        except CRMException as e:
            return Response(error_response(e.code, e.message), status=e.status_code)

    def post(self, request):
        try:
            user = get_current_user_from_request(request)
            if not user.has_perm("can_view_cashbox") and user.role not in ("owner", "admin", "support"):
                return Response(error_response("forbidden", "Cashbox permission required"), status=403)

            data = request.data
            cashbox = data.get("cashbox", "Основная касса")
            opening_cash = Decimal(str(data.get("opening_cash", "0.00")))

            uow = DjangoFinanceUnitOfWork()
            shift = OpenShiftUseCase(uow).execute(
                company_id=uuid.UUID(user.company_id),
                user_id=uuid.UUID(user.user_id),
                cashbox=cashbox,
                opening_cash=opening_cash,
            )
            return Response({
                "id": shift.id,
                "cashbox": shift.cashbox,
                "opening_cash": str(shift.opening_cash),
                "status": shift.status,
                "opened_at": shift.opened_at,
            }, status=201)
        except CRMException as e:
            return Response(error_response(e.code, e.message, e.details), status=e.status_code)


class ShiftCloseView(APIView):
    def post(self, request, shift_id):
        try:
            user = get_current_user_from_request(request)
            if not user.has_perm("can_view_cashbox") and user.role not in ("owner", "admin", "support"):
                return Response(error_response("forbidden", "Cashbox permission required"), status=403)

            data = request.data
            closing_cash = Decimal(str(data.get("closing_cash", "0.00")))
            sales_total = Decimal(str(data.get("sales_total", "0.00")))
            sales_count = int(data.get("sales_count", 0))

            uow = DjangoFinanceUnitOfWork()
            shift = CloseShiftUseCase(uow).execute(
                company_id=uuid.UUID(user.company_id),
                shift_id=uuid.UUID(str(shift_id)),
                closing_cash=closing_cash,
                sales_total=sales_total,
                sales_count=sales_count,
            )
            return Response({
                "id": shift.id,
                "status": shift.status,
                "closing_cash": str(shift.closing_cash),
                "sales_total": str(shift.sales_total),
                "closed_at": shift.closed_at,
            })
        except CRMException as e:
            return Response(error_response(e.code, e.message, e.details), status=e.status_code)


class SalaryAccrualsView(APIView):
    def get(self, request):
        try:
            user = get_current_user_from_request(request)
            if not user.has_perm("can_view_salary"):
                return Response(error_response("forbidden", "Salary permission required"), status=403)

            master_id = request.query_params.get("master_id")
            repo = DjangoAccrualRepository()
            if master_id:
                accruals = repo.list_by_master(uuid.UUID(user.company_id), uuid.UUID(master_id))
            else:
                accruals = repo.list_by_company(uuid.UUID(user.company_id))

            results = [
                {
                    "id": str(a.id),
                    "appointment_id": str(a.appointment_id),
                    "master_id": str(a.master_id),
                    "service_id": str(a.service_id) if a.service_id else None,
                    "amount": str(a.amount.amount),
                    "percent": float(a.percent),
                    "created_at": a.created_at.isoformat(),
                }
                for a in accruals
            ]
            return Response(results)
        except CRMException as e:
            return Response(error_response(e.code, e.message), status=e.status_code)


class SalaryPayoutsView(APIView):
    def get(self, request):
        try:
            user = get_current_user_from_request(request)
            if not user.has_perm("can_view_salary"):
                return Response(error_response("forbidden", "Salary permission required"), status=403)

            master_id = request.query_params.get("master_id")
            repo = DjangoSalaryPayoutRepository()
            if master_id:
                payouts = repo.list_by_master(uuid.UUID(user.company_id), uuid.UUID(master_id))
            else:
                payouts = repo.list_by_company(uuid.UUID(user.company_id))

            results = [
                {
                    "id": str(p.id),
                    "master_id": str(p.master_id),
                    "amount": str(p.amount.amount),
                    "date": p.date.isoformat(),
                    "cashbox": p.cashbox,
                    "comment": p.comment,
                    "created_at": p.created_at.isoformat(),
                }
                for p in payouts
            ]
            return Response(results)
        except CRMException as e:
            return Response(error_response(e.code, e.message), status=e.status_code)

    def post(self, request):
        try:
            user = get_current_user_from_request(request)
            if not user.has_perm("can_view_salary"):
                return Response(error_response("forbidden", "Salary permission required"), status=403)

            data = request.data
            master_id = uuid.UUID(data["master_id"])
            amount = Decimal(str(data["amount"]))
            p_date = date.fromisoformat(data["date"]) if "date" in data else date.today()
            cashbox = data.get("cashbox", "Основная касса")
            comment = data.get("comment")

            uow = DjangoFinanceUnitOfWork()
            payout = RegisterPayoutUseCase(uow).execute(
                company_id=uuid.UUID(user.company_id),
                master_id=master_id,
                amount=amount,
                payout_date=p_date,
                cashbox=cashbox,
                comment=comment,
            )
            return Response({
                "id": payout.id,
                "master_id": payout.master_id,
                "amount": str(payout.amount),
                "date": payout.date,
                "cashbox": payout.cashbox,
            }, status=201)
        except CRMException as e:
            return Response(error_response(e.code, e.message, e.details), status=e.status_code)


class SalarySummaryView(APIView):
    def get(self, request):
        try:
            user = get_current_user_from_request(request)
            if not user.has_perm("can_view_salary"):
                return Response(error_response("forbidden", "Salary permission required"), status=403)

            master_id_str = request.query_params.get("master_id")
            master_id = uuid.UUID(master_id_str) if master_id_str else None

            uow = DjangoFinanceUnitOfWork()
            summary = GetSalarySummaryUseCase(uow).execute(uuid.UUID(user.company_id), master_id)
            return Response({
                "accrued_total": str(summary.accrued_total),
                "paid_total": str(summary.paid_total),
                "balance": str(summary.balance),
            })
        except CRMException as e:
            return Response(error_response(e.code, e.message), status=e.status_code)


class WarehouseMaterialsView(APIView):
    def get(self, request):
        try:
            user = get_current_user_from_request(request)
            repo = DjangoWarehouseRepository()
            materials = repo.list_materials(uuid.UUID(user.company_id))
            return Response([
                {
                    "id": str(m.id),
                    "name": m.name,
                    "unit": m.unit,
                    "current_stock": str(m.current_stock),
                    "cost_price": str(m.cost_price.amount),
                }
                for m in materials
            ])
        except CRMException as e:
            return Response(error_response(e.code, e.message), status=e.status_code)

    def post(self, request):
        try:
            user = get_current_user_from_request(request)
            data = request.data
            mat = Material(
                id=uuid.uuid4(),
                company_id=uuid.UUID(user.company_id),
                name=data["name"],
                unit=data.get("unit", "шт"),
                current_stock=Decimal(str(data.get("current_stock", "0.000"))),
                cost_price=Money(Decimal(str(data.get("cost_price", "0.00")))),
            )
            repo = DjangoWarehouseRepository()
            repo.save_material(mat)
            return Response({"id": str(mat.id), "name": mat.name}, status=201)
        except CRMException as e:
            return Response(error_response(e.code, e.message, e.details), status=e.status_code)


# Internal API views
class InternalProcessCompletedAppointmentView(APIView):
    def post(self, request):
        try:
            verify_internal_service_request(request, "finance-service")
            data = request.data
            company_id = uuid.UUID(data["company_id"])
            appointment_id = uuid.UUID(data["appointment_id"])
            master_id = uuid.UUID(data["master_id"])
            price = Decimal(str(data.get("price", "0.00")))
            services = data.get("services", [])

            uow = DjangoFinanceUnitOfWork()
            catalog_client = HttpCatalogClient()
            accrual = ProcessAppointmentCompletedUseCase(uow, catalog_client).execute(
                company_id=company_id,
                appointment_id=appointment_id,
                master_id=master_id,
                price=price,
                services=services,
            )
            if not accrual:
                return Response({"status": "already_processed"})
            return Response({
                "id": accrual.id,
                "amount": str(accrual.amount),
                "percent": float(accrual.percent),
            }, status=201)
        except CRMException as e:
            return Response(error_response(e.code, e.message, e.details), status=e.status_code)
