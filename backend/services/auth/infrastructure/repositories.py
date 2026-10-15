from typing import Optional, List
import uuid
from backend.services.auth.domain.models import Company, Employee, Session
from backend.services.auth.domain.repositories import CompanyRepository, EmployeeRepository, SessionRepository
from backend.services.auth.infrastructure.models import CompanyModel, EmployeeModel, SessionModel


class DjangoCompanyRepository(CompanyRepository):
    def _to_domain(self, m: CompanyModel) -> Company:
        c = Company(
            id=m.id,
            company_id=m.id,
            name=m.name,
            slug=m.slug,
            industry=m.industry,
            sector=m.sector,
            appointment_work_start=m.appointment_work_start,
            appointment_work_end=m.appointment_work_end,
            subscription_plan=m.subscription_plan,
            created_at=m.created_at,
            updated_at=m.updated_at,
        )
        return c

    def get_by_id(self, company_id: uuid.UUID) -> Optional[Company]:
        try:
            m = CompanyModel.objects.get(id=company_id)
            return self._to_domain(m)
        except CompanyModel.DoesNotExist:
            return None

    def get_by_slug(self, slug: str) -> Optional[Company]:
        try:
            m = CompanyModel.objects.get(slug=slug)
            return self._to_domain(m)
        except CompanyModel.DoesNotExist:
            return None

    def save(self, company: Company) -> None:
        CompanyModel.objects.update_or_create(
            id=company.id,
            defaults={
                "name": company.name,
                "slug": company.slug,
                "industry": company.industry,
                "sector": company.sector,
                "appointment_work_start": company.appointment_work_start,
                "appointment_work_end": company.appointment_work_end,
                "subscription_plan": company.subscription_plan,
            },
        )


class DjangoEmployeeRepository(EmployeeRepository):
    def _to_domain(self, m: EmployeeModel) -> Employee:
        branch_uuids = [uuid.UUID(str(b)) for b in m.branch_ids] if m.branch_ids else []
        return Employee(
            id=m.id,
            company_id=m.company_id,
            first_name=m.first_name,
            last_name=m.last_name,
            email=m.email,
            password_hash=m.password_hash,
            phone_number=m.phone_number,
            role=m.role,
            role_display=m.role_display,
            avatar=m.avatar,
            branch_ids=branch_uuids,
            is_active=m.is_active,
            version=m.version,
            created_at=m.created_at,
            updated_at=m.updated_at,
        )

    def get_by_id(self, company_id: uuid.UUID, employee_id: uuid.UUID) -> Optional[Employee]:
        try:
            m = EmployeeModel.objects.get(company_id=company_id, id=employee_id)
            return self._to_domain(m)
        except EmployeeModel.DoesNotExist:
            return None

    def get_by_email(self, company_id: Optional[uuid.UUID], email: str) -> Optional[Employee]:
        try:
            qs = EmployeeModel.objects.filter(email=email)
            if company_id:
                qs = qs.filter(company_id=company_id)
            m = qs.first()
            if m:
                return self._to_domain(m)
            return None
        except EmployeeModel.DoesNotExist:
            return None

    def list_by_company(self, company_id: uuid.UUID, role: Optional[str] = None) -> List[Employee]:
        qs = EmployeeModel.objects.filter(company_id=company_id)
        if role:
            qs = qs.filter(role=role)
        return [self._to_domain(m) for m in qs]

    def save(self, employee: Employee) -> None:
        EmployeeModel.objects.update_or_create(
            id=employee.id,
            defaults={
                "company_id": employee.company_id,
                "first_name": employee.first_name,
                "last_name": employee.last_name,
                "email": employee.email,
                "password_hash": employee.password_hash,
                "phone_number": employee.phone_number,
                "role": employee.role,
                "role_display": employee.role_display,
                "avatar": employee.avatar,
                "branch_ids": [str(b) for b in employee.branch_ids],
                "is_active": employee.is_active,
                "version": employee.version,
            },
        )


class DjangoSessionRepository(SessionRepository):
    def _to_domain(self, m: SessionModel) -> Session:
        return Session(
            id=m.id,
            company_id=m.company_id,
            user_id=m.user_id,
            device=m.device,
            ip_address=m.ip_address,
            refresh_token_hash=m.refresh_token_hash,
            is_revoked=m.is_revoked,
            last_seen=m.last_seen,
            created_at=m.created_at,
        )

    def get_by_id(self, session_id: uuid.UUID) -> Optional[Session]:
        try:
            m = SessionModel.objects.get(id=session_id)
            return self._to_domain(m)
        except SessionModel.DoesNotExist:
            return None

    def save(self, session: Session) -> None:
        SessionModel.objects.update_or_create(
            id=session.id,
            defaults={
                "company_id": session.company_id,
                "user_id": session.user_id,
                "device": session.device,
                "ip_address": session.ip_address,
                "refresh_token_hash": session.refresh_token_hash,
                "is_revoked": session.is_revoked,
            },
        )

    def revoke(self, session_id: uuid.UUID) -> None:
        SessionModel.objects.filter(id=session_id).update(is_revoked=True)

    def revoke_all_for_user(self, user_id: uuid.UUID) -> None:
        SessionModel.objects.filter(user_id=user_id).update(is_revoked=True)
