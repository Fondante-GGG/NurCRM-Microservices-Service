from __future__ import annotations
import uuid
from decimal import Decimal
from typing import List, Optional, Protocol

from libs.common.domain import Money
from libs.common.events import EventEnvelope, EventTypes
from libs.common.exceptions import NotFoundError, VersionConflictError, ValidationError
from backend.services.catalog.domain.models import ServiceCategory, Service, SalaryRate
from backend.services.catalog.domain.repositories import ServiceCategoryRepository, ServiceRepository, SalaryRateRepository
from backend.services.catalog.application.dto import (
    CreateServiceDTO,
    UpdateServiceDTO,
    ServiceDTO,
    ServiceCategoryDTO,
    SalaryRateDTO,
)


class CatalogUnitOfWork(Protocol):
    categories: ServiceCategoryRepository
    services: ServiceRepository
    rates: SalaryRateRepository

    def __enter__(self) -> "CatalogUnitOfWork":
        ...

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        ...

    def commit(self) -> None:
        ...

    def record_outbox(self, event: EventEnvelope) -> None:
        ...


class CreateCategoryUseCase:
    def __init__(self, uow: CatalogUnitOfWork):
        self.uow = uow

    def execute(self, company_id: uuid.UUID, name: str, is_active: bool = True) -> ServiceCategoryDTO:
        with self.uow:
            category = ServiceCategory(
                id=uuid.uuid4(),
                company_id=company_id,
                name=name,
                is_active=is_active,
            )
            self.uow.categories.save(category)
            self.uow.commit()
            return ServiceCategoryDTO(
                id=str(category.id),
                company_id=str(category.company_id),
                name=category.name,
                is_active=category.is_active,
                version=category.version,
            )


class CreateServiceUseCase:
    def __init__(self, uow: CatalogUnitOfWork):
        self.uow = uow

    def execute(self, dto: CreateServiceDTO) -> ServiceDTO:
        with self.uow:
            category = self.uow.categories.get_by_id(dto.company_id, dto.category_id)
            if not category:
                raise NotFoundError(f"Category {dto.category_id} not found")

            service = Service(
                id=uuid.uuid4(),
                company_id=dto.company_id,
                category_id=dto.category_id,
                name=dto.name,
                price=Money(dto.price),
                time_minutes=dto.time_minutes,
                barbers=dto.barbers,
                is_active=dto.is_active,
            )
            self.uow.services.save(service)

            # Record event: catalog.service.changed
            event = EventEnvelope(
                type=EventTypes.CATALOG_SERVICE_CHANGED,
                company_id=str(dto.company_id),
                data={
                    "service_id": str(service.id),
                    "category_id": str(service.category_id),
                    "name": service.name,
                    "price": str(service.price.amount),
                    "time_minutes": service.time_minutes,
                    "barbers": [str(b) for b in service.barbers],
                    "is_active": service.is_active,
                    "action": "created",
                },
            )
            self.uow.record_outbox(event)
            self.uow.commit()

            return ServiceDTO(
                id=str(service.id),
                company_id=str(service.company_id),
                category_id=str(service.category_id),
                name=service.name,
                price=service.price.amount,
                time_minutes=service.time_minutes,
                barbers=[str(b) for b in service.barbers],
                is_active=service.is_active,
                version=service.version,
            )


class UpdateServiceUseCase:
    def __init__(self, uow: CatalogUnitOfWork):
        self.uow = uow

    def execute(self, company_id: uuid.UUID, service_id: uuid.UUID, dto: UpdateServiceDTO) -> ServiceDTO:
        with self.uow:
            service = self.uow.services.get_by_id(company_id, service_id)
            if not service:
                raise NotFoundError(f"Service {service_id} not found")

            if dto.expected_version is not None and dto.expected_version != service.version:
                raise VersionConflictError(current_version=service.version)

            if dto.name is not None:
                service.name = dto.name
            if dto.category_id is not None:
                service.category_id = dto.category_id
            if dto.price is not None:
                service.price = Money(dto.price)
            if dto.time_minutes is not None:
                service.time_minutes = dto.time_minutes
            if dto.barbers is not None:
                service.barbers = dto.barbers
            if dto.is_active is not None:
                service.is_active = dto.is_active

            service.increment_version()
            self.uow.services.save(service)

            event = EventEnvelope(
                type=EventTypes.CATALOG_SERVICE_CHANGED,
                company_id=str(company_id),
                data={
                    "service_id": str(service.id),
                    "name": service.name,
                    "price": str(service.price.amount),
                    "time_minutes": service.time_minutes,
                    "is_active": service.is_active,
                    "action": "updated",
                },
            )
            self.uow.record_outbox(event)
            self.uow.commit()

            return ServiceDTO(
                id=str(service.id),
                company_id=str(service.company_id),
                category_id=str(service.category_id),
                name=service.name,
                price=service.price.amount,
                time_minutes=service.time_minutes,
                barbers=[str(b) for b in service.barbers],
                is_active=service.is_active,
                version=service.version,
            )


class SetSalaryRateUseCase:
    def __init__(self, uow: CatalogUnitOfWork):
        self.uow = uow

    def execute(self, company_id: uuid.UUID, service_id: uuid.UUID, percent: Decimal, master_id: Optional[uuid.UUID] = None) -> SalaryRateDTO:
        with self.uow:
            service = self.uow.services.get_by_id(company_id, service_id)
            if not service:
                raise NotFoundError(f"Service {service_id} not found")

            rate = self.uow.rates.get_rate(company_id, service_id, master_id)
            if not rate:
                rate = SalaryRate(
                    id=uuid.uuid4(),
                    company_id=company_id,
                    service_id=service_id,
                    master_id=master_id,
                    percent=percent,
                )
            else:
                rate.percent = percent
                rate.increment_version()

            self.uow.rates.save(rate)
            self.uow.commit()

            return SalaryRateDTO(
                id=str(rate.id),
                company_id=str(rate.company_id),
                service_id=str(rate.service_id),
                master_id=str(rate.master_id) if rate.master_id else None,
                percent=rate.percent,
            )
