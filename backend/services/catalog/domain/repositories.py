from typing import Optional, List, Protocol
import uuid
from backend.services.catalog.domain.models import ServiceCategory, Service, SalaryRate


class ServiceCategoryRepository(Protocol):
    def get_by_id(self, company_id: uuid.UUID, category_id: uuid.UUID) -> Optional[ServiceCategory]:
        ...

    def list_by_company(self, company_id: uuid.UUID, is_active_only: bool = False) -> List[ServiceCategory]:
        ...

    def save(self, category: ServiceCategory) -> None:
        ...

    def delete(self, company_id: uuid.UUID, category_id: uuid.UUID) -> None:
        ...


class ServiceRepository(Protocol):
    def get_by_id(self, company_id: uuid.UUID, service_id: uuid.UUID) -> Optional[Service]:
        ...

    def list_by_ids(self, company_id: uuid.UUID, service_ids: List[uuid.UUID]) -> List[Service]:
        ...

    def list_by_company(self, company_id: uuid.UUID, category_id: Optional[uuid.UUID] = None, is_active_only: bool = False) -> List[Service]:
        ...

    def save(self, service: Service) -> None:
        ...

    def delete(self, company_id: uuid.UUID, service_id: uuid.UUID) -> None:
        ...


class SalaryRateRepository(Protocol):
    def get_rate(self, company_id: uuid.UUID, service_id: uuid.UUID, master_id: Optional[uuid.UUID] = None) -> Optional[SalaryRate]:
        ...

    def list_by_company(self, company_id: uuid.UUID) -> List[SalaryRate]:
        ...

    def save(self, rate: SalaryRate) -> None:
        ...
