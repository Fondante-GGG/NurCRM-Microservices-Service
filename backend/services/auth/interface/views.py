from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
import uuid

from libs.common.auth import KeyManager, verify_token, verify_internal_token
from libs.common.exceptions import UnauthorizedError, ForbiddenError, NotFoundError, CRMException
from libs.common.response import error_response
from backend.services.auth.application.dto import LoginRequestDTO, CreateEmployeeDTO
from backend.services.auth.application.use_cases import LoginUseCase, RefreshUseCase, CreateEmployeeUseCase
from backend.services.auth.infrastructure.uow import DjangoAuthUnitOfWork
from backend.services.auth.infrastructure.repositories import DjangoCompanyRepository, DjangoEmployeeRepository


def get_current_user_from_request(request):
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise UnauthorizedError("Missing or invalid Authorization header")
    token = auth_header.split(" ")[1]
    return verify_token(token)


class JWKSView(APIView):
    def get(self, request):
        return Response(KeyManager.get_jwks())


class LoginView(APIView):
    def post(self, request):
        try:
            email = request.data.get("email")
            password = request.data.get("password")
            if not email or not password:
                return Response(
                    error_response("validation_error", "Email and password are required"),
                    status=status.HTTP_400_BAD_REQUEST,
                )

            ip = request.META.get("REMOTE_ADDR")
            device = request.META.get("HTTP_USER_AGENT")

            dto = LoginRequestDTO(email=email, password=password, device=device, ip_address=ip)
            uow = DjangoAuthUnitOfWork()
            result = LoginUseCase(uow).execute(dto)

            return Response({
                "access": result.access_token,
                "refresh": result.refresh_token,
                "access_token": result.access_token,
                "refresh_token": result.refresh_token,
                "company_id": result.company_id,
                "user_id": result.user_id,
                "user": {
                    "id": result.user_id,
                    "company_id": result.company_id,
                    "first_name": result.first_name,
                    "last_name": result.last_name,
                    "email": result.email,
                    "role": result.role,
                    "permissions": result.permissions,
                    "company_slug": result.company_slug,
                }
            })
        except CRMException as e:
            return Response(error_response(e.code, e.message, e.details), status=e.status_code)
        except Exception as e:
            return Response(error_response("internal_error", str(e)), status=500)


class RefreshView(APIView):
    def post(self, request):
        try:
            refresh_token = request.data.get("refresh") or request.data.get("refresh_token")
            if not refresh_token:
                return Response(
                    error_response("validation_error", "refresh token is required"),
                    status=status.HTTP_400_BAD_REQUEST,
                )
            uow = DjangoAuthUnitOfWork()
            res = RefreshUseCase(uow).execute(refresh_token)
            return Response({"access": res["access_token"]})
        except CRMException as e:
            return Response(error_response(e.code, e.message, e.details), status=e.status_code)


class ProfileView(APIView):
    def get(self, request):
        try:
            user = get_current_user_from_request(request)
            repo = DjangoEmployeeRepository()
            emp = repo.get_by_id(uuid.UUID(user.company_id), uuid.UUID(user.user_id))
            if not emp:
                return Response(error_response("not_found", "Employee not found"), status=404)

            return Response({
                "id": str(emp.id),
                "company_id": str(emp.company_id),
                "first_name": emp.first_name,
                "last_name": emp.last_name,
                "email": emp.email,
                "phone_number": emp.phone_number,
                "role": emp.role,
                "role_display": emp.role_display,
                "avatar": emp.avatar,
                "permissions": user.permissions,
            })
        except CRMException as e:
            return Response(error_response(e.code, e.message), status=e.status_code)


class CompanyView(APIView):
    def get(self, request):
        try:
            user = get_current_user_from_request(request)
            repo = DjangoCompanyRepository()
            company = repo.get_by_id(uuid.UUID(user.company_id))
            if not company:
                return Response(error_response("not_found", "Company not found"), status=404)

            return Response({
                "id": str(company.id),
                "name": company.name,
                "slug": company.slug,
                "industry": company.industry,
                "sector": company.sector,
                "appointment_work_start": str(company.appointment_work_start),
                "appointment_work_end": str(company.appointment_work_end),
                "subscription_plan": company.subscription_plan,
            })
        except CRMException as e:
            return Response(error_response(e.code, e.message), status=e.status_code)


class EmployeeListView(APIView):
    def get(self, request):
        try:
            user = get_current_user_from_request(request)
            role = request.query_params.get("role")
            repo = DjangoEmployeeRepository()
            employees = repo.list_by_company(uuid.UUID(user.company_id), role=role)
            return Response({
                "count": len(employees),
                "results": [
                    {
                        "id": str(e.id),
                        "first_name": e.first_name,
                        "last_name": e.last_name,
                        "email": e.email,
                        "phone_number": e.phone_number,
                        "role": e.role,
                        "role_display": e.role_display,
                        "avatar": e.avatar,
                        "branch_ids": [str(b) for b in e.branch_ids],
                        "is_active": e.is_active,
                    }
                    for e in employees
                ]
            })
        except CRMException as e:
            return Response(error_response(e.code, e.message), status=e.status_code)

    def post(self, request):
        try:
            user = get_current_user_from_request(request)
            if user.role != "owner" and user.role != "admin":
                return Response(error_response("forbidden", "Only owner or admin can create employees"), status=403)

            data = request.data
            dto = CreateEmployeeDTO(
                company_id=uuid.UUID(user.company_id),
                first_name=data["first_name"],
                last_name=data["last_name"],
                email=data["email"],
                password=data["password"],
                phone_number=data["phone_number"],
                role=data.get("role", "master"),
                role_display=data.get("role_display", "Специалист"),
                avatar=data.get("avatar"),
            )
            uow = DjangoAuthUnitOfWork()
            emp = CreateEmployeeUseCase(uow).execute(dto)
            return Response({
                "id": str(emp.id),
                "first_name": emp.first_name,
                "last_name": emp.last_name,
                "email": emp.email,
                "role": emp.role,
                "role_display": emp.role_display,
            }, status=201)
        except CRMException as e:
            return Response(error_response(e.code, e.message, e.details), status=e.status_code)


# Internal API views
class InternalCompanyView(APIView):
    def get(self, request, company_id=None, slug=None):
        repo = DjangoCompanyRepository()
        if company_id:
            c = repo.get_by_id(uuid.UUID(str(company_id)))
        elif slug:
            c = repo.get_by_slug(slug)
        else:
            return Response(error_response("validation_error", "company_id or slug required"), status=400)

        if not c:
            return Response(error_response("not_found", "Company not found"), status=404)

        return Response({
            "id": str(c.id),
            "name": c.name,
            "slug": c.slug,
            "appointment_work_start": str(c.appointment_work_start),
            "appointment_work_end": str(c.appointment_work_end),
            "subscription_plan": c.subscription_plan,
        })


class InternalMastersView(APIView):
    def get(self, request):
        company_id = request.query_params.get("company_id")
        slug = request.query_params.get("slug")
        c_repo = DjangoCompanyRepository()
        if slug and not company_id:
            c = c_repo.get_by_slug(slug)
            if not c:
                return Response(error_response("not_found", "Company slug not found"), status=404)
            company_id = str(c.id)

        if not company_id:
            return Response(error_response("validation_error", "company_id or slug required"), status=400)

        emp_repo = DjangoEmployeeRepository()
        masters = emp_repo.list_by_company(uuid.UUID(company_id))
        return Response([
            {
                "id": str(m.id),
                "first_name": m.first_name,
                "last_name": m.last_name,
                "role": m.role,
                "role_display": m.role_display,
                "avatar": m.avatar,
                "is_active": m.is_active,
            }
            for m in masters if m.is_active
        ])
