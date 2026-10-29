import uuid
from decimal import Decimal

import pytest

from backend.services.inventory.domain.models import StockBalance
from backend.services.pos.application.use_cases import CheckoutUseCase
from backend.services.pos.domain.models import CatalogProduct
from libs.common.exceptions import ConflictError, ValidationError


class InMemorySaleRepository:
    def __init__(self):
        self.sales = {}

    def get_by_idempotency_key(self, company_id, idempotency_key, request_hash):
        sale = self.sales.get((company_id, idempotency_key))
        if sale and sale.request_hash != request_hash:
            raise ConflictError("Idempotency key was already used with a different checkout payload")
        return sale

    def create_or_get(self, sale):
        key = (sale.company_id, sale.idempotency_key)
        existing = self.sales.get(key)
        if existing:
            if existing.request_hash != sale.request_hash:
                raise ConflictError("Idempotency key was already used with a different payload")
            return existing, False
        self.sales[key] = sale
        return sale, True

    def set_reservation(self, sale_id, reservation_id):
        sale = next(sale for sale in self.sales.values() if sale.id == sale_id)
        sale.inventory_reservation_id = reservation_id

    def set_status(self, sale_id, status):
        sale = next(sale for sale in self.sales.values() if sale.id == sale_id)
        sale.status = status


class FakeCatalogClient:
    def __init__(self, products):
        self.products = products
        self.calls = 0

    def get_products(self, company_id, product_ids):
        self.calls += 1
        return [product for product in self.products if product.id in product_ids]


class FakeInventoryClient:
    def __init__(self, reserve_error=None):
        self.reservation_id = uuid.uuid4()
        self.reserve_error = reserve_error
        self.reserve_calls = []
        self.commit_calls = []

    def reserve(self, company_id, idempotency_key, items):
        self.reserve_calls.append((company_id, idempotency_key, items))
        if self.reserve_error:
            raise self.reserve_error
        return self.reservation_id

    def commit(self, company_id, reservation_id):
        self.commit_calls.append((company_id, reservation_id))


def _checkout_fixture(reserve_error=None):
    company_id = uuid.uuid4()
    cashier_id = uuid.uuid4()
    product = CatalogProduct(
        id=uuid.uuid4(),
        name="Shampoo",
        sku="SH-01",
        price=Decimal("10.00"),
        unit_code="pcs",
        minimum_quantity=Decimal("0.500"),
        quantity_step=Decimal("0.500"),
        is_active=True,
    )
    repository = InMemorySaleRepository()
    catalog = FakeCatalogClient([product])
    inventory = FakeInventoryClient(reserve_error=reserve_error)
    use_case = CheckoutUseCase(repository, catalog, inventory)
    payload = {
        "items": [
            {
                "product_id": str(product.id),
                "quantity": "1.5",
                "unit_code": "pcs",
            }
        ],
        "discount": "1.00",
    }
    return company_id, cashier_id, payload, repository, catalog, inventory, use_case


def test_checkout_reserves_commits_and_is_idempotent():
    company_id, cashier_id, payload, _, catalog, inventory, use_case = _checkout_fixture()

    sale, created = use_case.execute(company_id, cashier_id, "checkout-1", payload)
    catalog.products = []
    retry, retry_created = use_case.execute(company_id, cashier_id, "checkout-1", payload)

    assert created is True
    assert retry_created is False
    assert retry.id == sale.id
    assert sale.status == "completed"
    assert sale.total.amount == Decimal("14.00")
    assert sale.inventory_reservation_id == inventory.reservation_id
    assert len(inventory.reserve_calls) == 1
    assert len(inventory.commit_calls) == 1
    assert catalog.calls == 1


def test_checkout_marks_sale_rejected_when_stock_is_insufficient():
    stock_error = ConflictError("Insufficient stock", code="stock_insufficient")
    company_id, cashier_id, payload, repository, _, inventory, use_case = _checkout_fixture(stock_error)

    with pytest.raises(ConflictError):
        use_case.execute(company_id, cashier_id, "checkout-2", payload)

    sale = next(iter(repository.sales.values()))
    assert sale.status == "rejected"
    assert inventory.commit_calls == []


def test_checkout_rejects_non_object_payload_before_service_calls():
    company_id, cashier_id, _, _, _, inventory, use_case = _checkout_fixture()

    with pytest.raises(ValidationError, match="checkout object"):
        use_case.execute(company_id, cashier_id, "checkout-3", [])

    assert inventory.reserve_calls == []
    assert inventory.commit_calls == []


def test_checkout_rejects_mixed_branch_items():
    company_id, cashier_id, payload, _, _, inventory, use_case = _checkout_fixture()
    payload["items"].append(
        {
            "product_id": payload["items"][0]["product_id"],
            "quantity": "0.5",
            "unit_code": "pcs",
            "branch_id": str(uuid.uuid4()),
        }
    )

    with pytest.raises(ValidationError, match="same branch"):
        use_case.execute(company_id, cashier_id, "checkout-4", payload)

    assert inventory.reserve_calls == []


def test_stock_balance_reserve_release_and_consume():
    balance = StockBalance(
        id=uuid.uuid4(),
        company_id=uuid.uuid4(),
        product_id=uuid.uuid4(),
        quantity=Decimal("5.000"),
    )

    balance.reserve(Decimal("2.000"))
    assert balance.available == Decimal("3.000")
    balance.release(Decimal("0.500"))
    assert balance.reserved == Decimal("1.500")
    balance.consume(Decimal("1.500"))
    assert balance.quantity == Decimal("3.500")
    assert balance.reserved == Decimal("0.000")


def test_stock_balance_rejects_reservation_over_available_quantity():
    balance = StockBalance(
        id=uuid.uuid4(),
        company_id=uuid.uuid4(),
        product_id=uuid.uuid4(),
        quantity=Decimal("1.000"),
    )

    with pytest.raises(ConflictError) as error:
        balance.reserve(Decimal("1.001"))

    assert error.value.code == "stock_insufficient"
