from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
import uuid
from decimal import Decimal
from datetime import date, time

from libs.common.auth import verify_token, verify_internal_service_request
from libs.common.exceptions import UnauthorizedError, ForbiddenError, CRMException, NotFoundError
from libs.common.response import error_response
from libs.common.pagination import PaginationParams, paginate_results
from backend.services.booking.application.dto import CreateBookingRequestDTO
from backend.services.booking.application.use_cases import CreateBookingRequestUseCase, ConfirmBookingSagaUseCase
from backend.services.booking.infrastructure.uow import DjangoBookingUnitOfWork
from backend.services.booking.infrastructure.repositories import DjangoBookingRequestRepository
from backend.services.booking.infrastructure.clients import HttpClientServiceClient, HttpScheduleServiceClient


def get_current_user_from_request(request):
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise UnauthorizedError("Missing or invalid Authorization header")
    token = auth_header.split(" ")[1]
    return verify_token(token)


class BookingListCreateView(APIView):
    def get(self, request):
        try:
            user = get_current_user_from_request(request)
            status_param = request.query_params.get("status")
            repo = DjangoBookingRequestRepository()
            bookings = repo.list_by_company(uuid.UUID(user.company_id), status=status_param)

            params = PaginationParams.from_request_params(
                request.query_params.get("limit"), request.query_params.get("offset")
            )
            total = len(bookings)
            paginated = bookings[params.offset : params.offset + params.limit]

            results = [
                {
                    "id": str(b.id),
                    "client_name": b.client_name,
                    "client_phone": str(b.client_phone),
                    "services": b.services,
                    "master_id": str(b.master_id) if b.master_id else None,
                    "date": b.date.isoformat(),
                    "time_start": b.time_start.isoformat(),
                    "time_end": b.time_end.isoformat(),
                    "total_price": str(b.total_price.amount),
                    "total_duration_min": b.total_duration_min,
                    "payment_method": b.payment_method,
                    "client_comment": b.client_comment,
                    "status": b.status,
                    "appointment_id": str(b.appointment_id) if b.appointment_id else None,
                    "version": b.version,
                    "created_at": b.created_at.isoformat(),
                }
                for b in paginated
            ]
            return Response(paginate_results(results, total, params))
        except CRMException as e:
            return Response(error_response(e.code, e.message), status=e.status_code)

    def post(self, request):
        try:
            user = get_current_user_from_request(request)
            data = request.data
            d = date.fromisoformat(data["date"])
            t_start = time.fromisoformat(data["time_start"])
            t_end = time.fromisoformat(data["time_end"]) if "time_end" in data else time(t_start.hour, t_start.minute + 30)
            master_id = uuid.UUID(data["master_id"]) if data.get("master_id") else None

            dto = CreateBookingRequestDTO(
                company_id=uuid.UUID(user.company_id),
                client_name=data["client_name"],
                client_phone=data["client_phone"],
                services=data.get("services", []),
                date=d,
                time_start=t_start,
                time_end=t_end,
                total_price=Decimal(str(data.get("total_price", "0.00"))),
                total_duration_min=int(data.get("total_duration_min", 30)),
                master_id=master_id,
                payment_method=data.get("payment_method", "cash"),
                client_comment=data.get("client_comment", ""),
            )
            uow = DjangoBookingUnitOfWork()
            res = CreateBookingRequestUseCase(uow).execute(dto)
            return Response({
                "id": res.id,
                "client_name": res.client_name,
                "status": res.status,
                "total_price": str(res.total_price),
                "created_at": res.created_at,
            }, status=201)
        except CRMException as e:
            return Response(error_response(e.code, e.message, e.details), status=e.status_code)


class BookingDetailView(APIView):
    def get(self, request, booking_id):
        try:
            user = get_current_user_from_request(request)
            repo = DjangoBookingRequestRepository()
            b = repo.get_by_id(uuid.UUID(user.company_id), uuid.UUID(str(booking_id)))
            if not b:
                return Response(error_response("not_found", "Booking request not found"), status=404)
            return Response({
                "id": str(b.id),
                "client_name": b.client_name,
                "client_phone": str(b.client_phone),
                "services": b.services,
                "master_id": str(b.master_id) if b.master_id else None,
                "date": b.date.isoformat(),
                "time_start": b.time_start.isoformat(),
                "time_end": b.time_end.isoformat(),
                "total_price": str(b.total_price.amount),
                "total_duration_min": b.total_duration_min,
                "status": b.status,
                "appointment_id": str(b.appointment_id) if b.appointment_id else None,
                "version": b.version,
            })
        except CRMException as e:
            return Response(error_response(e.code, e.message), status=e.status_code)

    def patch(self, request, booking_id):
        try:
            user = get_current_user_from_request(request)
            data = request.data
            target_status = data.get("status")

            uow = DjangoBookingUnitOfWork()

            if target_status == "confirmed":
                # Execute Saga
                client_client = HttpClientServiceClient()
                schedule_client = HttpScheduleServiceClient()
                saga = ConfirmBookingSagaUseCase(uow, client_client, schedule_client)
                res = saga.execute(
                    company_id=uuid.UUID(user.company_id),
                    booking_id=uuid.UUID(str(booking_id)),
                    actor_name=user.email or user.user_id,
                )
                return Response({
                    "id": res.id,
                    "status": res.status,
                    "appointment_id": res.appointment_id,
                    "version": res.version,
                })
            else:
                # Update status (e.g. spam, no_show)
                with uow:
                    b = uow.bookings.get_by_id(uuid.UUID(user.company_id), uuid.UUID(str(booking_id)))
                    if not b:
                        return Response(error_response("not_found", "Booking not found"), status=404)
                    if target_status:
                        b.status = target_status
                        b.increment_version()
                    uow.bookings.save(b)
                    uow.commit()
                    return Response({"id": str(b.id), "status": b.status, "version": b.version})
        except CRMException as e:
            return Response(error_response(e.code, e.message, e.details), status=e.status_code)


class InternalBookingCreateView(APIView):
    """Used by public-gateway to create online booking request."""

    def post(self, request):
        try:
            verify_internal_service_request(request, "booking-service")
            data = request.data
            d = date.fromisoformat(data["date"])
            t_start = time.fromisoformat(data["time_start"])
            t_end = time.fromisoformat(data["time_end"]) if "time_end" in data else time(t_start.hour, t_start.minute + 30)
            master_id = uuid.UUID(data["master_id"]) if data.get("master_id") else None

            dto = CreateBookingRequestDTO(
                company_id=uuid.UUID(data["company_id"]),
                client_name=data["client_name"],
                client_phone=data["client_phone"],
                services=data.get("services", []),
                date=d,
                time_start=t_start,
                time_end=t_end,
                total_price=Decimal(str(data.get("total_price", "0.00"))),
                total_duration_min=int(data.get("total_duration_min", 30)),
                master_id=master_id,
                payment_method=data.get("payment_method", "cash"),
                client_comment=data.get("client_comment", ""),
            )
            uow = DjangoBookingUnitOfWork()
            res = CreateBookingRequestUseCase(uow).execute(dto)
            return Response({
                "id": res.id,
                "client_name": res.client_name,
                "status": res.status,
                "total_price": str(res.total_price),
                "created_at": res.created_at,
            }, status=201)
        except CRMException as e:
            return Response(error_response(e.code, e.message, e.details), status=e.status_code)
