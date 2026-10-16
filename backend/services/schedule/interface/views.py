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
from backend.services.schedule.infrastructure.models import MasterShiftModel


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
                    "barber": str(a.barber_id) if a.barber_id else None,
                    "barber_id": str(a.barber_id) if a.barber_id else None,
                    "staff": str(a.barber_id) if a.barber_id else None,
                    "services": [s.to_dict() for s in a.services],
                    "start": a.start_at.isoformat(),
                    "start_at": a.start_at.isoformat(),
                    "end_at": a.end_at.isoformat(),
                    "duration": int((a.end_at - a.start_at).total_seconds() // 60),
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
            data = request.data or {}

            # 1. Services
            service_ids = []
            for s in data.get("services", []):
                if isinstance(s, dict) and "service_id" in s:
                    service_ids.append(uuid.UUID(str(s["service_id"])))
                elif isinstance(s, dict) and "id" in s:
                    service_ids.append(uuid.UUID(str(s["id"])))
                else:
                    service_ids.append(uuid.UUID(str(s)))

            # 2. Start time (if flow or not provided, defaults to now())
            start_raw = data.get("start") or data.get("start_at")
            if start_raw:
                start_at = datetime.fromisoformat(str(start_raw).replace("Z", "+00:00"))
            else:
                start_at = datetime.now(timezone.utc)

            client_id = uuid.UUID(str(data["client_id"])) if data.get("client_id") else None

            # 3. Staff / Barber (can be empty in flow queue)
            barber_raw = data.get("staff") or data.get("barber") or data.get("barber_id")
            barber_id = uuid.UUID(str(barber_raw)) if barber_raw else None

            # 4. Status (flow default pending, otherwise booked)
            default_status = "pending" if barber_id is None else "booked"
            status_val = data.get("status") or default_status

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
                status=status_val,
            )
            uow = DjangoScheduleUnitOfWork()
            catalog_client = HttpCatalogClient()
            res = CreateAppointmentUseCase(uow, catalog_client).execute(dto)
            return Response({
                "id": res.id,
                "client_id": res.client_id,
                "client_name": res.client_name,
                "staff": res.barber_id,
                "barber_id": res.barber_id,
                "barber": res.barber_id,
                "services": res.services,
                "start": res.start_at,
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
                "staff": str(a.barber_id) if a.barber_id else None,
                "barber_id": str(a.barber_id) if a.barber_id else None,
                "barber": str(a.barber_id) if a.barber_id else None,
                "services": [s.to_dict() for s in a.services],
                "start": a.start_at.isoformat(),
                "start_at": a.start_at.isoformat(),
                "end_at": a.end_at.isoformat(),
                "duration": int((a.end_at - a.start_at).total_seconds() // 60),
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
            data = request.data or {}
            if_match = request.headers.get("If-Match")
            expected_ver = int(if_match) if if_match and if_match.isdigit() else data.get("expected_version")

            uow = DjangoScheduleUnitOfWork()

            barber_raw = data.get("staff") or data.get("barber_id") or data.get("barber")
            barber_id = uuid.UUID(str(barber_raw)) if barber_raw else None
            new_status = data.get("status")

            service_ids = None
            if "services" in data:
                service_ids = []
                for s in data["services"]:
                    if isinstance(s, dict) and "service_id" in s:
                        service_ids.append(uuid.UUID(str(s["service_id"])))
                    elif isinstance(s, dict) and "id" in s:
                        service_ids.append(uuid.UUID(str(s["id"])))
                    else:
                        service_ids.append(uuid.UUID(str(s)))

            start_raw = data.get("start") or data.get("start_at")
            start_at = datetime.fromisoformat(str(start_raw).replace("Z", "+00:00")) if start_raw else None
            disc = Decimal(str(data["discount"])) if "discount" in data and data["discount"] is not None else None

            dto = UpdateAppointmentDTO(
                start_at=start_at,
                barber_id=barber_id,
                service_ids=service_ids,
                client_name=data.get("client_name"),
                discount=disc,
                comment=data.get("comment"),
                status=new_status,
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
                "staff": res.barber_id,
                "barber_id": res.barber_id,
                "barber": res.barber_id,
                "start": res.start_at,
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


VALID_SHIFT_FACTS = ["planned", "worked", "missed", "busy"]


class ShiftListCreateView(APIView):
    def get(self, request):
        try:
            user = get_current_user_from_request(request)
            qs = MasterShiftModel.objects.filter(company_id=uuid.UUID(user.company_id))

            master_id = request.query_params.get("master_id") or request.query_params.get("staff")
            if master_id:
                qs = qs.filter(master_id=uuid.UUID(master_id))

            date_param = request.query_params.get("date")
            if date_param:
                qs = qs.filter(date=date.fromisoformat(date_param))

            fact_param = request.query_params.get("fact")
            if fact_param:
                qs = qs.filter(fact=fact_param)

            shifts = [
                {
                    "id": str(s.id),
                    "company_id": str(s.company_id),
                    "master_id": str(s.master_id),
                    "staff": str(s.master_id),
                    "date": s.date.isoformat(),
                    "fact": s.fact,
                    "start_time": str(s.start_time),
                    "end_time": str(s.end_time),
                }
                for s in qs.order_by("date", "start_time")
            ]
            return Response(shifts)
        except CRMException as e:
            return Response(error_response(e.code, e.message), status=e.status_code)

    def post(self, request):
        try:
            user = get_current_user_from_request(request)
            data = request.data or {}

            master_raw = data.get("master_id") or data.get("staff")
            if not master_raw:
                return Response(error_response("validation_error", "master_id or staff is required"), status=400)
            master_id = uuid.UUID(str(master_raw))

            date_str = data.get("date")
            if not date_str:
                shift_date = date.today()
            else:
                shift_date = date.fromisoformat(str(date_str))

            fact = data.get("fact", "planned")
            if fact not in VALID_SHIFT_FACTS:
                return Response(error_response("invalid_fact", f"fact must be one of {VALID_SHIFT_FACTS}"), status=400)

            start_time = data.get("start_time", "09:00:00")
            end_time = data.get("end_time", "21:00:00")

            shift = MasterShiftModel.objects.create(
                company_id=uuid.UUID(user.company_id),
                master_id=master_id,
                date=shift_date,
                fact=fact,
                start_time=start_time,
                end_time=end_time,
            )

            return Response({
                "id": str(shift.id),
                "company_id": str(shift.company_id),
                "master_id": str(shift.master_id),
                "staff": str(shift.master_id),
                "date": shift.date.isoformat(),
                "fact": shift.fact,
                "start_time": str(shift.start_time),
                "end_time": str(shift.end_time),
            }, status=201)
        except CRMException as e:
            return Response(error_response(e.code, e.message), status=e.status_code)


class ShiftDetailView(APIView):
    def get(self, request, shift_id):
        try:
            user = get_current_user_from_request(request)
            try:
                shift = MasterShiftModel.objects.get(id=uuid.UUID(str(shift_id)), company_id=uuid.UUID(user.company_id))
            except MasterShiftModel.DoesNotExist:
                return Response(error_response("not_found", "Shift not found"), status=404)

            return Response({
                "id": str(shift.id),
                "company_id": str(shift.company_id),
                "master_id": str(shift.master_id),
                "staff": str(shift.master_id),
                "date": shift.date.isoformat(),
                "fact": shift.fact,
                "start_time": str(shift.start_time),
                "end_time": str(shift.end_time),
            })
        except CRMException as e:
            return Response(error_response(e.code, e.message), status=e.status_code)

    def patch(self, request, shift_id):
        try:
            user = get_current_user_from_request(request)
            try:
                shift = MasterShiftModel.objects.get(id=uuid.UUID(str(shift_id)), company_id=uuid.UUID(user.company_id))
            except MasterShiftModel.DoesNotExist:
                return Response(error_response("not_found", "Shift not found"), status=404)

            data = request.data or {}
            if "fact" in data:
                fact = data["fact"]
                if fact not in VALID_SHIFT_FACTS:
                    return Response(
                        error_response("invalid_fact", f"fact must be one of {VALID_SHIFT_FACTS}"),
                        status=400,
                    )
                shift.fact = fact

            if "start_time" in data:
                shift.start_time = data["start_time"]
            if "end_time" in data:
                shift.end_time = data["end_time"]

            shift.save()

            return Response({
                "id": str(shift.id),
                "company_id": str(shift.company_id),
                "master_id": str(shift.master_id),
                "staff": str(shift.master_id),
                "date": shift.date.isoformat(),
                "fact": shift.fact,
                "start_time": str(shift.start_time),
                "end_time": str(shift.end_time),
            })
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
