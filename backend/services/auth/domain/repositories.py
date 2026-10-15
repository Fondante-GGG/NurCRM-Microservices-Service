from typing import Optional, List, Protocol
import uuid
from backend.services.auth.domain.models import Company, Employee, Session


class CompanyRepository(Protocol):
    def get_by_id(self, company_id: uuid.UUID) -> Optional[Company]:
        ...

    def get_by_slug(self, slug: str) -> Optional[Company]:
        ...

    def save(self, company: Company) -> None:
        ...


class EmployeeRepository(Protocol):
    def get_by_id(self, company_id: uuid.UUID, employee_id: uuid.UUID) -> Optional[Employee]:
        ...

    def get_by_email(self, company_id: Optional[uuid.UUID], email: str) -> Optional[Employee]:
        ...

    def list_by_company(self, company_id: uuid.UUID, role: Optional[str] = None) -> List[Employee]:
        ...

    def save(self, employee: Employee) -> None:
        ...


class SessionRepository(Protocol):
    def get_by_id(self, session_id: uuid.UUID) -> Optional[Session]:
        ...

    def save(self, session: Session) -> None:
        ...

    def revoke(self, session_id: uuid.UUID) -> None:
        ...

    def revoke_all_for_user(self, user_id: uuid.UUID) -> None:
        ...
