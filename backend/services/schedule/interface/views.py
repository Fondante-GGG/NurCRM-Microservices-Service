from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
import uuid
from decimal import Decimal
from datetime import datetime, date, timezone

from libs.common.auth import verify_token
from libs.common.exceptions import UnauthorizedError, ForbiddenError, CRMException, NotFoundError, SlotBusyError
from libs.common.response import error_response
from libs.common.pagination import PaginationParams, paginate_results
from backend.services.schedule.application.dto import CreateAppointmentDTO, UpdateAppointmentDTO
from backend.services.schedule.application.use_cases import (
    CreateAppointmentUseCase,
    UpdateAppointmentUseCase,
    ChangeAppointmentStatusUseCase,
    AutoCompleteAppointmentsUseCase,
    GetBusyIntervalsUseCase,
)
from backend.services.schedule.infrastructure.uow import DjangoScheduleUnitOfWork
from backend.services.schedule.infrastructure.repositories import DjangoAppointmentRepository
from backend.services.schedule.infrastructure.catalog_client import HttpCatalogClient


def get_current_user_from_request(request):
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise UnauthorizedError("Missing or invalid Authorization header")
    token = auth_header.split(" ")[1]
    return verify_token(token)


class AppointmentListCreateView(APIView):
    def get(self, request):
        try:
            user = get_current_user_from_request(request)
            barber_id = request.query_params.get("barber_id")
            barber_uuid = uuid.UUID(barber_id) if barber_id else None

            # Date filters
            date_str = request.query_params.get("date")
            date_from_str = request.query_params.get("date_from")
            date_to_str = request.query_params.get("date_to")
            status_param = request.query_params.get("status")

            date_from = None
            date_to = None
            if date_str:
                d = date.fromisoformat(date_str)
                date_from = datetime(d.year, d.month, d.day, 0, 0, 0, tzinfo=timezone.utc)
                date_to = datetime(d.year, d.month, d.day, 23, 59, 59, tzinfo=timezone.utc)
            elif date_from_str:
                date_from = datetime.fromisoformat(date_from_str)
                if date_to_str:
                    date_to = datetime.fromisoformat(date_to_str)

            repo = DjangoAppointmentRepository()
            appts = repo.list_by_company(
                company_id=uuid.UUID(user.company_id),
                barber_id=barber_uuid,
                date_from=date_from,
                date_to=date_to,
                status=status_param,
            )

            params = PaginationParams.from_request_params(
                request.query_params.get("limit"), request.query_params.get("offset")
            )
            total = len(appts)
            paginated = appts[params.offset : params.offset + params.limit]

            results = [
                {
                    "id": str(a.id),
                    "client_id": str(a.client_id) if a.client_id else None,
                    "client_name": a.client_name,
                    "barber": str(a.barber_id),
                    "barber_id": str(a.barber_id),
                    "services": [s.to_dict() for s in a.services],
                    "start_at": a.start_at.isoformat(),
                    "end_at": a.end_at.isoformat(),
                    "price": str(a.price.amount),
                    "discount": str(a.discount.amount),
                    "status": a.status,
                    "comment": a.comment,
                    "version": a.version,
                    "created_at": a.created_at.isoformat(),
                }
                for a in paginated
            ]
            return Response(paginate_results(results, total, params))
        except CRMException as e:
            return Response(error_response(e.code, e.message), status=e.status_code)

    def post(self, request):
        try:
            user = get_current_user_from_request(request)
            data = request.data
            service_ids = [uuid.UUID(str(s)) for s in data.get("services", [])]

            start_at = datetime.fromisoformat(data["start_at"])
            client_id = uuid.UUID(data["client_id"]) if data.get("client_id") else None
            barber_id = uuid.UUID(data.get("barber") or data.get("barber_id"))
            disc = Decimal(str(data["discount"])) if "discount" in data and data["discount"] is not None else None

            dto = CreateAppointmentDTO(
                company_id=uuid.UUID(user.company_id),
                client_name=data.get("client_name", "Клиент"),
                barber_id=barber_id,
                start_at=start_at,
                service_ids=service_ids,
                client_id=client_id,
                discount=disc,
                comment=data.get("comment", ""),
                status=data.get("status", "booked"),
            )
            uow = DjangoScheduleUnitOfWork()
            catalog_client = HttpCatalogClient()
            res = CreateAppointmentUseCase(uow, catalog_client).execute(dto)
            return Response({
                "id": res.id,
                "client_id": res.client_id,
                "client_name": res.client_name,
                "barber_id": res.barber_id,
                "services": res.services,
                "start_at": res.start_at,
                "end_at": res.end_at,
                "price": str(res.price),
                "status": res.status,
                "version": res.version,
            }, status=201)
        except CRMException as e:
            return Response(error_response(e.code, e.message, e.details), status=e.status_code)


class AppointmentDetailView(APIView):
    def get(self, request, appt_id):
        try:
            user = get_current_user_from_request(request)
            repo = DjangoAppointmentRepository()
            a = repo.get_by_id(uuid.UUID(user.company_id), uuid.UUID(str(appt_id)))
            if not a:
                return Response(error_response("not_found", "Appointment not found"), status=404)
            return Response({
                "id": str(a.id),
                "client_id": str(a.client_id) if a.client_id else None,
                "client_name": a.client_name,
                "barber_id": str(a.barber_id),
                "services": [s.to_dict() for s in a.services],
                "start_at": a.start_at.isoformat(),
                "end_at": a.end_at.isoformat(),
                "price": str(a.price.amount),
                "discount": str(a.discount.amount),
                "status": a.status,
                "comment": a.comment,
                "version": a.version,
            })
        except CRMException as e:
            return Response(error_response(e.code, e.message), status=e.status_code)

    def patch(self, request, appt_id):
        try:
            user = get_current_user_from_request(request)
            data = request.data
            if_match = request.headers.get("If-Match")
            expected_ver = int(if_match) if if_match and if_match.isdigit() else data.get("expected_version")

            uow = DjangoScheduleUnitOfWork()

            # Check if this is a simple status transition
            if "status" in data and len(data) <= 2:
                res = ChangeAppointmentStatusUseCase(uow).execute(
                    company_id=uuid.UUID(user.company_id),
                    appt_id=uuid.UUID(str(appt_id)),
                    new_status=data["status"],
                    expected_version=expected_ver,
                )
            else:
                service_ids = [uuid.UUID(str(s)) for s in data["services"]] if "services" in data else None
                start_at = datetime.fromisoformat(data["start_at"]) if "start_at" in data else None
                barber_id = uuid.UUID(data["barber_id"]) if "barber_id" in data else None
                disc = Decimal(str(data["discount"])) if "discount" in data else None

                dto = UpdateAppointmentDTO(
                    start_at=start_at,
                    barber_id=barber_id,
                    service_ids=service_ids,
                    client_name=data.get("client_name"),
                    discount=disc,
                    comment=data.get("comment"),
                    expected_version=expected_ver,
                )
                catalog_client = HttpCatalogClient()
                res = UpdateAppointmentUseCase(uow, catalog_client).execute(
                    company_id=uuid.UUID(user.company_id),
                    appt_id=uuid.UUID(str(appt_id)),
                    dto=dto,
                )

            return Response({
                "id": res.id,
                "status": res.status,
                "start_at": res.start_at,
                "end_at": res.end_at,
                "price": str(res.price),
                "version": res.version,
            })
        except CRMException as e:
            return Response(error_response(e.code, e.message, e.details), status=e.status_code)

    def delete(self, request, appt_id):
        try:
            user = get_current_user_from_request(request)
            uow = DjangoScheduleUnitOfWork()
            res = ChangeAppointmentStatusUseCase(uow).execute(
                company_id=uuid.UUID(user.company_id),
                appt_id=uuid.UUID(str(appt_id)),
                new_status="canceled",
            )
            return Response(status=204)
        except CRMException as e:
            return Response(error_response(e.code, e.message), status=e.status_code)


class MyAppointmentsView(APIView):
    """Personal schedule view for the currently logged-in master."""

    def get(self, request):
        try:
            user = get_current_user_from_request(request)
            repo = DjangoAppointmentRepository()
            appts = repo.list_by_company(
                company_id=uuid.UUID(user.company_id),
                barber_id=uuid.UUID(user.user_id),
            )
            results = [
                {
                    "id": str(a.id),
                    "client_name": a.client_name,
                    "services": [s.to_dict() for s in a.services],
                    "start_at": a.start_at.isoformat(),
                    "end_at": a.end_at.isoformat(),
                    "status": a.status,
                    "version": a.version,
                }
                for a in appts
            ]
            return Response(results)
        except CRMException as e:
            return Response(error_response(e.code, e.message), status=e.status_code)


# Internal API views
class InternalBusySlotsView(APIView):
    def get(self, request):
        company_id = request.query_params.get("company_id")
        barber_id = request.query_params.get("master_id") or request.query_params.get("barber_id")
        date_str = request.query_params.get("date")

        if not company_id or not barber_id or not date_str:
            return Response(error_response("validation_error", "company_id, master_id, and date are required"), status=400)

        target_date = date.fromisoformat(date_str)
        uow = DjangoScheduleUnitOfWork()
        busy = GetBusyIntervalsUseCase(uow).execute(
            company_id=uuid.UUID(company_id),
            barber_id=uuid.UUID(barber_id),
            target_date=target_date,
        )
        return Response([{"start_at": b.start_at, "end_at": b.end_at} for b in busy])


class InternalAutoCompleteView(APIView):
    def post(self, request):
        uow = DjangoScheduleUnitOfWork()
        count = AutoCompleteAppointmentsUseCase(uow).execute()
        return Response({"completed_count": count})


class InternalCreateAppointmentView(APIView):
    def post(self, request):
        try:
            data = request.data
            service_ids = [uuid.UUID(str(s)) for s in data.get("services", [])]
            start_at = datetime.fromisoformat(data["start_at"])
            client_id = uuid.UUID(data["client_id"]) if data.get("client_id") else None
            barber_id = uuid.UUID(data.get("barber_id") or data.get("barber"))
            disc = Decimal(str(data["discount"])) if "discount" in data and data["discount"] is not None else None

            dto = CreateAppointmentDTO(
                company_id=uuid.UUID(data["company_id"]),
                client_name=data.get("client_name", "Клиент"),
                barber_id=barber_id,
                start_at=start_at,
                service_ids=service_ids,
                client_id=client_id,
                discount=disc,
                comment=data.get("comment", ""),
                status=data.get("status", "confirmed"),
            )
            uow = DjangoScheduleUnitOfWork()
            catalog_client = HttpCatalogClient()
            res = CreateAppointmentUseCase(uow, catalog_client).execute(dto)
            return Response({
                "id": res.id,
                "status": res.status,
                "start_at": res.start_at,
                "end_at": res.end_at,
                "price": str(res.price),
                "version": res.version,
            }, status=201)
        except CRMException as e:
            return Response(error_response(e.code, e.message, e.details), status=e.status_code)
