-- POS and retail inventory schemas. Safe to run once on existing deployments.
CREATE SCHEMA IF NOT EXISTS inventory;
CREATE SCHEMA IF NOT EXISTS pos;

DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'svc_inventory') THEN
        CREATE ROLE svc_inventory WITH LOGIN PASSWORD 'svc_inventory_secret';
    END IF;
    IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'svc_pos') THEN
        CREATE ROLE svc_pos WITH LOGIN PASSWORD 'svc_pos_secret';
    END IF;
END
$$;

ALTER ROLE svc_inventory SET search_path = inventory, public;
ALTER ROLE svc_pos SET search_path = pos, public;

GRANT USAGE, CREATE ON SCHEMA inventory TO svc_inventory;
GRANT USAGE, CREATE ON SCHEMA pos TO svc_pos;
GRANT USAGE ON SCHEMA inventory, pos TO svc_admin, svc_analytics;

CREATE TABLE IF NOT EXISTS catalog.products (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    company_id UUID NOT NULL,
    name VARCHAR(255) NOT NULL,
    sku VARCHAR(64) NOT NULL DEFAULT '',
    category VARCHAR(255) NOT NULL DEFAULT '',
    price NUMERIC(12,2) NOT NULL DEFAULT 0,
    cost_price NUMERIC(12,2) NOT NULL DEFAULT 0,
    wholesale_price NUMERIC(12,2),
    unit_code VARCHAR(32) NOT NULL DEFAULT 'pcs',
    minimum_quantity NUMERIC(12,3) NOT NULL DEFAULT 1,
    quantity_step NUMERIC(12,3) NOT NULL DEFAULT 1,
    attributes JSONB NOT NULL DEFAULT '{}',
    is_active BOOLEAN NOT NULL DEFAULT true,
    version INT NOT NULL DEFAULT 1,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT ck_catalog_product_price_nonnegative CHECK (price >= 0),
    CONSTRAINT ck_catalog_product_cost_nonnegative CHECK (cost_price >= 0),
    CONSTRAINT ck_catalog_product_minimum_nonnegative CHECK (minimum_quantity >= 0),
    CONSTRAINT ck_catalog_product_wholesale_nonnegative CHECK (wholesale_price IS NULL OR wholesale_price >= 0),
    CONSTRAINT ck_catalog_product_step_positive CHECK (quantity_step > 0)
);
CREATE INDEX IF NOT EXISTS idx_catalog_products_company ON catalog.products(company_id, name);
CREATE UNIQUE INDEX IF NOT EXISTS uq_catalog_product_company_sku
    ON catalog.products(company_id, sku) WHERE sku <> '';

CREATE TABLE IF NOT EXISTS inventory.stock_balances (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    company_id UUID NOT NULL,
    product_id UUID NOT NULL,
    variant_id UUID,
    branch_id UUID,
    location_code VARCHAR(64) NOT NULL DEFAULT 'default',
    quantity NUMERIC(14,3) NOT NULL DEFAULT 0,
    reserved NUMERIC(14,3) NOT NULL DEFAULT 0,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_inventory_stock_scope UNIQUE NULLS NOT DISTINCT
        (company_id, product_id, variant_id, branch_id, location_code),
    CONSTRAINT ck_inventory_quantity_nonnegative CHECK (quantity >= 0),
    CONSTRAINT ck_inventory_reserved_nonnegative CHECK (reserved >= 0),
    CONSTRAINT ck_inventory_reserved_lte_quantity CHECK (reserved <= quantity)
);
CREATE INDEX IF NOT EXISTS idx_inventory_stock_product ON inventory.stock_balances(company_id, product_id);

CREATE TABLE IF NOT EXISTS inventory.stock_movements (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    company_id UUID NOT NULL,
    product_id UUID NOT NULL,
    variant_id UUID,
    branch_id UUID,
    location_code VARCHAR(64) NOT NULL DEFAULT 'default',
    movement_type VARCHAR(32) NOT NULL,
    quantity NUMERIC(14,3) NOT NULL,
    source_key VARCHAR(128) NOT NULL DEFAULT '',
    reason TEXT NOT NULL DEFAULT '',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT ck_inventory_movement_quantity_positive CHECK (quantity > 0)
);
CREATE INDEX IF NOT EXISTS idx_inventory_movements_product
    ON inventory.stock_movements(company_id, product_id, created_at);
CREATE UNIQUE INDEX IF NOT EXISTS uq_inventory_movement_source
    ON inventory.stock_movements(company_id, source_key) WHERE source_key <> '';

CREATE TABLE IF NOT EXISTS inventory.stock_reservations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    company_id UUID NOT NULL,
    idempotency_key VARCHAR(128) NOT NULL,
    status VARCHAR(16) NOT NULL DEFAULT 'reserved',
    items JSONB NOT NULL DEFAULT '[]',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_inventory_reservation_idempotency UNIQUE (company_id, idempotency_key),
    CONSTRAINT ck_inventory_reservation_status CHECK (status IN ('reserved', 'committed', 'released'))
);

CREATE TABLE IF NOT EXISTS inventory.outbox (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    event_id UUID NOT NULL,
    event_type VARCHAR(255) NOT NULL,
    payload JSONB NOT NULL,
    status VARCHAR(32) NOT NULL DEFAULT 'pending',
    retry_count INT NOT NULL DEFAULT 0,
    error TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    published_at TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS idx_inventory_outbox_pending
    ON inventory.outbox(status) WHERE status = 'pending';
CREATE TABLE IF NOT EXISTS inventory.inbox (
    event_id UUID PRIMARY KEY,
    event_type VARCHAR(255) NOT NULL,
    processed_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS pos.sales (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    company_id UUID NOT NULL,
    cashier_id UUID NOT NULL,
    branch_id UUID,
    idempotency_key VARCHAR(128) NOT NULL,
    request_hash VARCHAR(64) NOT NULL,
    inventory_reservation_id UUID,
    payment_method VARCHAR(32) NOT NULL DEFAULT 'cash',
    source VARCHAR(32) NOT NULL DEFAULT 'pos',
    device_id VARCHAR(128) NOT NULL DEFAULT '',
    discount NUMERIC(12,2) NOT NULL DEFAULT 0,
    total NUMERIC(12,2) NOT NULL DEFAULT 0,
    status VARCHAR(32) NOT NULL DEFAULT 'pending_inventory',
    sold_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_pos_sale_idempotency UNIQUE (company_id, idempotency_key),
    CONSTRAINT ck_pos_sale_discount_nonnegative CHECK (discount >= 0),
    CONSTRAINT ck_pos_sale_total_nonnegative CHECK (total >= 0),
    CONSTRAINT ck_pos_sale_payment_method CHECK (payment_method IN ('cash', 'card', 'transfer', 'debt')),
    CONSTRAINT ck_pos_sale_status CHECK (status IN ('pending_inventory', 'completed', 'rejected', 'returned'))
);
CREATE INDEX IF NOT EXISTS idx_pos_sales_company_created
    ON pos.sales(company_id, created_at DESC);

CREATE TABLE IF NOT EXISTS pos.sale_lines (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    sale_id UUID NOT NULL REFERENCES pos.sales(id) ON DELETE CASCADE,
    product_id UUID NOT NULL,
    variant_id UUID,
    branch_id UUID,
    location_code VARCHAR(64) NOT NULL DEFAULT 'default',
    name VARCHAR(255) NOT NULL,
    sku VARCHAR(64) NOT NULL DEFAULT '',
    quantity NUMERIC(12,3) NOT NULL,
    unit_code VARCHAR(32) NOT NULL,
    unit_price NUMERIC(12,2) NOT NULL,
    discount NUMERIC(12,2) NOT NULL DEFAULT 0,
    total NUMERIC(12,2) NOT NULL,
    CONSTRAINT ck_pos_line_quantity_positive CHECK (quantity > 0),
    CONSTRAINT ck_pos_line_price_nonnegative CHECK (unit_price >= 0),
    CONSTRAINT ck_pos_line_discount_nonnegative CHECK (discount >= 0),
    CONSTRAINT ck_pos_line_total_nonnegative CHECK (total >= 0)
);
CREATE INDEX IF NOT EXISTS idx_pos_sale_lines_sale ON pos.sale_lines(sale_id);

CREATE TABLE IF NOT EXISTS pos.outbox (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    event_id UUID NOT NULL,
    event_type VARCHAR(255) NOT NULL,
    payload JSONB NOT NULL,
    status VARCHAR(32) NOT NULL DEFAULT 'pending',
    retry_count INT NOT NULL DEFAULT 0,
    error TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    published_at TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS idx_pos_outbox_pending
    ON pos.outbox(status) WHERE status = 'pending';
CREATE TABLE IF NOT EXISTS pos.inbox (
    event_id UUID PRIMARY KEY,
    event_type VARCHAR(255) NOT NULL,
    processed_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA catalog TO svc_catalog;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA inventory TO svc_inventory;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA pos TO svc_pos;
GRANT SELECT ON catalog.products TO svc_admin;
GRANT SELECT ON ALL TABLES IN SCHEMA inventory, pos TO svc_analytics;
GRANT SELECT ON ALL TABLES IN SCHEMA inventory, pos TO svc_admin;
