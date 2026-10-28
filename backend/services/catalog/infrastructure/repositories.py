from typing import Optional, List
import uuid
from decimal import Decimal

from libs.common.domain import Money
from backend.services.catalog.domain.models import ServiceCategory, Service, SalaryRate, Product
from backend.services.catalog.domain.repositories import ServiceCategoryRepository, ServiceRepository, SalaryRateRepository
from backend.services.catalog.infrastructure.models import (
    ProductModel,
    ServiceCategoryModel,
    ServiceModel,
    SalaryRateModel,
)


class DjangoServiceCategoryRepository(ServiceCategoryRepository):
    def _to_domain(self, m: ServiceCategoryModel) -> ServiceCategory:
        return ServiceCategory(
            id=m.id,
            company_id=m.company_id,
            name=m.name,
            is_active=m.is_active,
            version=m.version,
            created_at=m.created_at,
            updated_at=m.updated_at,
        )

    def get_by_id(self, company_id: uuid.UUID, category_id: uuid.UUID) -> Optional[ServiceCategory]:
        try:
            m = ServiceCategoryModel.objects.get(company_id=company_id, id=category_id)
            return self._to_domain(m)
        except ServiceCategoryModel.DoesNotExist:
            return None

    def list_by_company(self, company_id: uuid.UUID, is_active_only: bool = False) -> List[ServiceCategory]:
        qs = ServiceCategoryModel.objects.filter(company_id=company_id)
        if is_active_only:
            qs = qs.filter(is_active=True)
        return [self._to_domain(m) for m in qs]

    def save(self, category: ServiceCategory) -> None:
        ServiceCategoryModel.objects.update_or_create(
            id=category.id,
            defaults={
                "company_id": category.company_id,
                "name": category.name,
                "is_active": category.is_active,
                "version": category.version,
            },
        )

    def delete(self, company_id: uuid.UUID, category_id: uuid.UUID) -> None:
        ServiceCategoryModel.objects.filter(company_id=company_id, id=category_id).delete()


class DjangoServiceRepository(ServiceRepository):
    def _to_domain(self, m: ServiceModel) -> Service:
        barbers = [uuid.UUID(str(b)) for b in m.barbers] if m.barbers else []
        return Service(
            id=m.id,
            company_id=m.company_id,
            category_id=m.category_id,
            name=m.name,
            price=Money(m.price),
            time_minutes=m.time_minutes,
            barbers=barbers,
            is_active=m.is_active,
            version=m.version,
            created_at=m.created_at,
            updated_at=m.updated_at,
        )

    def get_by_id(self, company_id: uuid.UUID, service_id: uuid.UUID) -> Optional[Service]:
        try:
            m = ServiceModel.objects.get(company_id=company_id, id=service_id)
            return self._to_domain(m)
        except ServiceModel.DoesNotExist:
            return None

    def list_by_ids(self, company_id: uuid.UUID, service_ids: List[uuid.UUID]) -> List[Service]:
        qs = ServiceModel.objects.filter(company_id=company_id, id__in=service_ids)
        return [self._to_domain(m) for m in qs]

    def list_by_company(self, company_id: uuid.UUID, category_id: Optional[uuid.UUID] = None, is_active_only: bool = False) -> List[Service]:
        qs = ServiceModel.objects.filter(company_id=company_id)
        if category_id:
            qs = qs.filter(category_id=category_id)
        if is_active_only:
            qs = qs.filter(is_active=True)
        return [self._to_domain(m) for m in qs]

    def save(self, service: Service) -> None:
        ServiceModel.objects.update_or_create(
            id=service.id,
            defaults={
                "company_id": service.company_id,
                "category_id": service.category_id,
                "name": service.name,
                "price": service.price.amount,
                "time_minutes": service.time_minutes,
                "barbers": [str(b) for b in service.barbers],
                "is_active": service.is_active,
                "version": service.version,
            },
        )

    def delete(self, company_id: uuid.UUID, service_id: uuid.UUID) -> None:
        ServiceModel.objects.filter(company_id=company_id, id=service_id).delete()


class DjangoSalaryRateRepository(SalaryRateRepository):
    def _to_domain(self, m: SalaryRateModel) -> SalaryRate:
        return SalaryRate(
            id=m.id,
            company_id=m.company_id,
            service_id=m.service_id,
            master_id=m.master_id,
            percent=m.percent,
            created_at=m.created_at,
            updated_at=m.updated_at,
        )

    def get_rate(self, company_id: uuid.UUID, service_id: uuid.UUID, master_id: Optional[uuid.UUID] = None) -> Optional[SalaryRate]:
        try:
            # Check master-specific rate first
            if master_id:
                m = SalaryRateModel.objects.filter(company_id=company_id, service_id=service_id, master_id=master_id).first()
                if m:
                    return self._to_domain(m)
            # Fallback to general service rate
            m = SalaryRateModel.objects.filter(company_id=company_id, service_id=service_id, master_id__isnull=True).first()
            if m:
                return self._to_domain(m)
            return None
        except SalaryRateModel.DoesNotExist:
            return None

    def list_by_company(self, company_id: uuid.UUID) -> List[SalaryRate]:
        qs = SalaryRateModel.objects.filter(company_id=company_id)
        return [self._to_domain(m) for m in qs]

    def save(self, rate: SalaryRate) -> None:
        SalaryRateModel.objects.update_or_create(
            company_id=rate.company_id,
            service_id=rate.service_id,
            master_id=rate.master_id,
            defaults={"percent": rate.percent},
        )


class DjangoProductRepository:
    def _to_domain(self, model: ProductModel) -> Product:
        return Product(
            id=model.id,
            company_id=model.company_id,
            name=model.name,
            sku=model.sku,
            category=model.category,
            price=Money(model.price),
            cost_price=Money(model.cost_price),
            wholesale_price=Money(model.wholesale_price) if model.wholesale_price is not None else None,
            unit_code=model.unit_code,
            minimum_quantity=model.minimum_quantity,
            quantity_step=model.quantity_step,
            attributes=model.attributes,
            is_active=model.is_active,
            version=model.version,
        )

    def get_by_id(self, company_id: uuid.UUID, product_id: uuid.UUID) -> Optional[Product]:
        model = ProductModel.objects.filter(company_id=company_id, id=product_id).first()
        return self._to_domain(model) if model else None

    def list_by_company(self, company_id: uuid.UUID, active_only: bool = False) -> List[Product]:
        query = ProductModel.objects.filter(company_id=company_id).order_by("name", "id")
        if active_only:
            query = query.filter(is_active=True)
        return [self._to_domain(model) for model in query]

    def list_by_ids(self, company_id: uuid.UUID, product_ids: List[uuid.UUID]) -> List[Product]:
        query = ProductModel.objects.filter(company_id=company_id, id__in=product_ids, is_active=True)
        return [self._to_domain(model) for model in query]

    def save(self, product: Product) -> None:
        ProductModel.objects.update_or_create(
            id=product.id,
            defaults={
                "company_id": product.company_id,
                "name": product.name,
                "sku": product.sku,
                "category": product.category,
                "price": product.price.amount,
                "cost_price": product.cost_price.amount,
                "wholesale_price": product.wholesale_price.amount if product.wholesale_price else None,
                "unit_code": product.unit_code,
                "minimum_quantity": product.minimum_quantity,
                "quantity_step": product.quantity_step,
                "attributes": product.attributes,
                "is_active": product.is_active,
                "version": product.version,
            },
        )
