from __future__ import annotations
import uuid
import hashlib
from typing import Optional, Protocol, List

from libs.common.auth import create_access_token, create_refresh_token, verify_token, verify_refresh_token
from libs.common.exceptions import UnauthorizedError, NotFoundError, ValidationError, ConflictError
from libs.common.events import EventEnvelope, EventTypes
from libs.common.outbox import OutboxRecord
from backend.services.auth.domain.models import Company, Employee, Session
from backend.services.auth.domain.repositories import CompanyRepository, EmployeeRepository, SessionRepository
from backend.services.auth.application.dto import LoginRequestDTO, LoginResponseDTO, CreateEmployeeDTO


class AuthUnitOfWork(Protocol):
    companies: CompanyRepository
    employees: EmployeeRepository
    sessions: SessionRepository

    def __enter__(self) -> "AuthUnitOfWork":
        ...

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        ...

    def commit(self) -> None:
        ...

    def record_outbox(self, event: EventEnvelope) -> None:
        ...


class LoginUseCase:
    def __init__(self, uow: AuthUnitOfWork):
        self.uow = uow

    def execute(self, dto: LoginRequestDTO) -> LoginResponseDTO:
        with self.uow:
            employee = self.uow.employees.get_by_email(None, dto.email)
            if not employee or not employee.is_active:
                raise UnauthorizedError("Invalid email or password")

            if not employee.check_password(dto.password):
                raise UnauthorizedError("Invalid email or password")

            company = self.uow.companies.get_by_id(employee.company_id)
            if not company:
                raise NotFoundError("Company not found for employee")

            session_id = uuid.uuid4()
            refresh_token = create_refresh_token(
                user_id=str(employee.id),
                company_id=str(employee.company_id),
                sid=str(session_id),
            )
            refresh_hash = hashlib.sha256(refresh_token.encode("utf-8")).hexdigest()

            session = Session(
                id=session_id,
                company_id=employee.company_id,
                user_id=employee.id,
                refresh_token_hash=refresh_hash,
                device=dto.device,
                ip_address=dto.ip_address,
            )
            self.uow.sessions.save(session)

            access_token = create_access_token(
                user_id=str(employee.id),
                company_id=str(employee.company_id),
                role=employee.role,
                permissions=employee.permissions,
                sid=str(session_id),
                email=employee.email,
            )

            self.uow.commit()

            return LoginResponseDTO(
                access_token=access_token,
                refresh_token=refresh_token,
                user_id=str(employee.id),
                company_id=str(employee.company_id),
                role=employee.role,
                permissions=employee.permissions,
                first_name=employee.first_name,
                last_name=employee.last_name,
                email=employee.email,
                company_slug=company.slug,
            )


class RefreshUseCase:
    def __init__(self, uow: AuthUnitOfWork):
        self.uow = uow

    def execute(self, refresh_token: str) -> dict:
        jwt_user = verify_refresh_token(refresh_token)
        if not jwt_user.sid:
            raise UnauthorizedError("Invalid refresh token")

        with self.uow:
            session = self.uow.sessions.get_by_id(uuid.UUID(jwt_user.sid))
            if not session or session.is_revoked:
                raise UnauthorizedError("Session has been revoked")

            # Check refresh token hash if present
            current_hash = hashlib.sha256(refresh_token.encode("utf-8")).hexdigest()
            if session.refresh_token_hash and session.refresh_token_hash != current_hash:
                # Reuse detected: revoke session
                session.revoke()
                self.uow.sessions.save(session)
                raise UnauthorizedError("Refresh token reuse detected. Session revoked.")

            employee = self.uow.employees.get_by_id(
                uuid.UUID(jwt_user.company_id), uuid.UUID(jwt_user.user_id)
            )
            if not employee or not employee.is_active:
                raise UnauthorizedError("Employee inactive or not found")

            new_access_token = create_access_token(
                user_id=str(employee.id),
                company_id=str(employee.company_id),
                role=employee.role,
                permissions=employee.permissions,
                sid=jwt_user.sid,
                email=employee.email,
            )
            new_refresh_token = create_refresh_token(
                user_id=str(employee.id),
                company_id=str(employee.company_id),
                sid=jwt_user.sid,
            )
            session.refresh_token_hash = hashlib.sha256(new_refresh_token.encode("utf-8")).hexdigest()
            self.uow.sessions.save(session)

            return {
                "access_token": new_access_token,
                "refresh_token": new_refresh_token,
            }


class CreateEmployeeUseCase:
    def __init__(self, uow: AuthUnitOfWork):
        self.uow = uow

    def execute(self, dto: CreateEmployeeDTO) -> Employee:
        with self.uow:
            existing = self.uow.employees.get_by_email(dto.company_id, dto.email)
            if existing:
                raise ConflictError(
                    message=f"Employee with email {dto.email} already exists in this company",
                    code="employee_exists",
                )

            employee = Employee(
                id=uuid.uuid4(),
                company_id=dto.company_id,
                first_name=dto.first_name,
                last_name=dto.last_name,
                email=dto.email,
                password_hash=Employee.hash_password(dto.password),
                phone_number=dto.phone_number,
                role=dto.role,
                role_display=dto.role_display,
                avatar=dto.avatar,
                branch_ids=dto.branch_ids or [],
                is_active=True,
            )
            self.uow.employees.save(employee)

            # Record event
            event = EventEnvelope(
                type=EventTypes.AUTH_EMPLOYEE_CHANGED,
                company_id=str(dto.company_id),
                data={
                    "employee_id": str(employee.id),
                    "first_name": employee.first_name,
                    "last_name": employee.last_name,
                    "role": employee.role,
                    "role_display": employee.role_display,
                    "avatar": employee.avatar,
                    "is_active": employee.is_active,
                },
            )
            self.uow.record_outbox(event)
            self.uow.commit()
            return employee
