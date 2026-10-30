-- Migration 04: Kezek Bath & Sauna Mode and Commercial Rent Module
-- Schema isolation for 'bath' and 'rent' domains

CREATE SCHEMA IF NOT EXISTS bath;
CREATE SCHEMA IF NOT EXISTS rent;

-- Roles for bath and rent services
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'svc_bath') THEN
        CREATE ROLE svc_bath WITH LOGIN PASSWORD 'svc_bath_secret';
    END IF;
    IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'svc_rent') THEN
        CREATE ROLE svc_rent WITH LOGIN PASSWORD 'svc_rent_secret';
    END IF;
END $$;

--------------------------------------------------------------------------------
-- 1. BATH & SAUNA (сфера «Баня, сауна, SPA»)
--------------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS bath.locker_categories (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    company_id UUID NOT NULL,
    branch_id UUID NOT NULL,
    name VARCHAR(128) NOT NULL,
    code VARCHAR(8) NOT NULL,
    count INTEGER NOT NULL DEFAULT 20,
    sort INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_bath_lcat_comp ON bath.locker_categories(company_id, branch_id);

CREATE TABLE IF NOT EXISTS bath.lockers (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    company_id UUID NOT NULL,
    branch_id UUID NOT NULL,
    category_id UUID NOT NULL REFERENCES bath.locker_categories(id) ON DELETE CASCADE,
    number INTEGER NOT NULL,
    code VARCHAR(16) NOT NULL,
    is_broken BOOLEAN NOT NULL DEFAULT false,
    bracelet_tag VARCHAR(64) DEFAULT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_locker_code UNIQUE (company_id, branch_id, code)
);
CREATE INDEX IF NOT EXISTS idx_bath_lockers_comp ON bath.lockers(company_id, branch_id);

CREATE TABLE IF NOT EXISTS bath.locker_reservations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    company_id UUID NOT NULL,
    branch_id UUID NOT NULL,
    locker_id UUID NOT NULL REFERENCES bath.lockers(id) ON DELETE CASCADE,
    who VARCHAR(255) NOT NULL,
    reserve_time TIMESTAMPTZ NOT NULL,
    status VARCHAR(32) NOT NULL DEFAULT 'active', -- active, used, cancelled
    created_by UUID DEFAULT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_bath_reserv_comp ON bath.locker_reservations(company_id, locker_id, status);

CREATE TABLE IF NOT EXISTS bath.entry_tariffs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    company_id UUID NOT NULL,
    branch_id UUID NOT NULL,
    name VARCHAR(128) NOT NULL,
    price NUMERIC(12,2) NOT NULL DEFAULT 0,
    included_hours INTEGER NOT NULL DEFAULT 0, -- 0 = безлимит
    extra_per_hour NUMERIC(12,2) NOT NULL DEFAULT 0,
    is_subscription BOOLEAN NOT NULL DEFAULT false,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_bath_tariff_comp ON bath.entry_tariffs(company_id, branch_id);

CREATE TABLE IF NOT EXISTS bath.visits (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    company_id UUID NOT NULL,
    branch_id UUID NOT NULL,
    locker_id UUID NOT NULL REFERENCES bath.lockers(id),
    tariff_id UUID NOT NULL REFERENCES bath.entry_tariffs(id),
    client_id UUID DEFAULT NULL,
    group_id UUID DEFAULT NULL,
    started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    closed_at TIMESTAMPTZ DEFAULT NULL,
    status VARCHAR(32) NOT NULL DEFAULT 'open', -- open, paid, debt
    closed_by UUID DEFAULT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_bath_visits_comp ON bath.visits(company_id, branch_id, status);
CREATE INDEX IF NOT EXISTS idx_bath_visits_locker ON bath.visits(locker_id, status);

CREATE TABLE IF NOT EXISTS bath.visit_items (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    company_id UUID NOT NULL,
    branch_id UUID NOT NULL,
    visit_id UUID REFERENCES bath.visits(id) ON DELETE CASCADE,
    room_booking_id UUID DEFAULT NULL,
    source VARCHAR(32) NOT NULL, -- entry, bar, extra, service, rent, time
    name VARCHAR(255) NOT NULL,
    price NUMERIC(12,2) NOT NULL,
    qty INTEGER NOT NULL DEFAULT 1,
    cost NUMERIC(12,2) NOT NULL DEFAULT 0,
    employee_id UUID DEFAULT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at TIMESTAMPTZ DEFAULT NULL,
    deleted_by UUID DEFAULT NULL,
    delete_reason TEXT DEFAULT NULL
);
CREATE INDEX IF NOT EXISTS idx_bath_vitems_visit ON bath.visit_items(visit_id);

CREATE TABLE IF NOT EXISTS bath.bar_categories (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    company_id UUID NOT NULL,
    branch_id UUID NOT NULL,
    name VARCHAR(128) NOT NULL,
    sort INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS bath.bar_items (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    company_id UUID NOT NULL,
    branch_id UUID NOT NULL,
    category_id UUID REFERENCES bath.bar_categories(id) ON DELETE SET NULL,
    name VARCHAR(255) NOT NULL,
    price NUMERIC(12,2) NOT NULL,
    cost NUMERIC(12,2) NOT NULL DEFAULT 0,
    stock INTEGER DEFAULT NULL, -- NULL = не считаем
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_bath_bar_comp ON bath.bar_items(company_id, branch_id);

CREATE TABLE IF NOT EXISTS bath.extra_services (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    company_id UUID NOT NULL,
    branch_id UUID NOT NULL,
    name VARCHAR(255) NOT NULL,
    price NUMERIC(12,2) NOT NULL,
    cost NUMERIC(12,2) NOT NULL DEFAULT 0,
    created_by UUID DEFAULT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS bath.master_services (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    company_id UUID NOT NULL,
    branch_id UUID NOT NULL,
    name VARCHAR(255) NOT NULL,
    price NUMERIC(12,2) NOT NULL,
    role VARCHAR(64) NOT NULL DEFAULT 'Мастер',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS bath.rooms (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    company_id UUID NOT NULL,
    branch_id UUID NOT NULL,
    name VARCHAR(128) NOT NULL,
    capacity INTEGER NOT NULL DEFAULT 6,
    price_per_hour NUMERIC(12,2) NOT NULL DEFAULT 1000,
    min_hours INTEGER NOT NULL DEFAULT 2,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS bath.room_bookings (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    company_id UUID NOT NULL,
    branch_id UUID NOT NULL,
    room_id UUID NOT NULL REFERENCES bath.rooms(id) ON DELETE CASCADE,
    from_time TIMESTAMPTZ NOT NULL,
    to_time TIMESTAMPTZ NOT NULL,
    who VARCHAR(255) NOT NULL,
    prepaid NUMERIC(12,2) NOT NULL DEFAULT 0,
    status VARCHAR(32) NOT NULL DEFAULT 'booked', -- booked, active, closed
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_bath_room_bookings ON bath.room_bookings(room_id, from_time, to_time);

CREATE TABLE IF NOT EXISTS bath.client_subscriptions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    company_id UUID NOT NULL,
    client_id UUID NOT NULL,
    name VARCHAR(128) NOT NULL,
    visits_total INTEGER NOT NULL,
    visits_left INTEGER NOT NULL,
    valid_until DATE NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_bath_csub_client ON bath.client_subscriptions(company_id, client_id);

CREATE TABLE IF NOT EXISTS bath.notifications (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    company_id UUID NOT NULL,
    branch_id UUID NOT NULL,
    type VARCHAR(32) NOT NULL, -- purchase, stock_low, stock_out
    visit_id UUID DEFAULT NULL,
    text TEXT NOT NULL,
    amount NUMERIC(12,2) DEFAULT NULL,
    employee_id UUID DEFAULT NULL,
    read_by JSONB NOT NULL DEFAULT '[]',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_bath_notif_comp ON bath.notifications(company_id, created_at);

--------------------------------------------------------------------------------
-- 2. COMMERCIAL RENT (модуль «Аренда помещений»)
--------------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS rent.unit_types (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    company_id UUID NOT NULL,
    name VARCHAR(128) NOT NULL,
    is_system BOOLEAN NOT NULL DEFAULT false,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS rent.units (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    company_id UUID NOT NULL,
    branch_id UUID NOT NULL,
    unit_type_id UUID REFERENCES rent.unit_types(id) ON DELETE SET NULL,
    number VARCHAR(32) NOT NULL,
    floor INTEGER NOT NULL DEFAULT 1,
    area_sqm NUMERIC(10,2) NOT NULL,
    rate_per_sqm NUMERIC(12,2) NOT NULL,
    reservation_until DATE DEFAULT NULL,
    reservation_who VARCHAR(255) DEFAULT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_rent_unit_num UNIQUE (company_id, branch_id, number)
);
CREATE INDEX IF NOT EXISTS idx_rent_units_comp ON rent.units(company_id, branch_id, floor);

CREATE TABLE IF NOT EXISTS rent.tenants (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    company_id UUID NOT NULL,
    name VARCHAR(255) NOT NULL,
    legal_form VARCHAR(32) NOT NULL DEFAULT 'ИП', -- ИП, ОсОО, физлицо
    inn VARCHAR(32) NOT NULL DEFAULT '',
    contact_person VARCHAR(255) NOT NULL DEFAULT '',
    passport VARCHAR(64) NOT NULL DEFAULT '',
    phone VARCHAR(32) NOT NULL,
    activity_type VARCHAR(128) NOT NULL DEFAULT '',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_rent_tenants_comp ON rent.tenants(company_id);

CREATE TABLE IF NOT EXISTS rent.templates (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    company_id UUID NOT NULL,
    type VARCHAR(32) NOT NULL DEFAULT 'lease', -- lease, employment
    name VARCHAR(255) NOT NULL,
    content TEXT NOT NULL,
    raw_file_url VARCHAR(512) DEFAULT NULL,
    is_archived BOOLEAN NOT NULL DEFAULT false,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS rent.leases (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    company_id UUID NOT NULL,
    branch_id UUID NOT NULL,
    tenant_id UUID NOT NULL REFERENCES rent.tenants(id) ON DELETE CASCADE,
    template_id UUID REFERENCES rent.templates(id) ON DELETE SET NULL,
    unit_ids UUID[] NOT NULL,
    number VARCHAR(64) NOT NULL, -- например А-2026/031
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    monthly_rent NUMERIC(12,2) NOT NULL,
    payment_day INTEGER NOT NULL DEFAULT 5,
    deposit NUMERIC(12,2) NOT NULL DEFAULT 0,
    penalty_pct NUMERIC(5,2) NOT NULL DEFAULT 0.1, -- 0.1% в день
    indexation_pct NUMERIC(5,2) NOT NULL DEFAULT 0,
    utilities NUMERIC(12,2) NOT NULL DEFAULT 0,
    status VARCHAR(32) NOT NULL DEFAULT 'active', -- active, draft, expiring, expired
    contract_text_snapshot TEXT NOT NULL DEFAULT '',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_rent_lease_number UNIQUE (company_id, number)
);
CREATE INDEX IF NOT EXISTS idx_rent_leases_comp ON rent.leases(company_id, branch_id, status);

CREATE TABLE IF NOT EXISTS rent.charges (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    company_id UUID NOT NULL,
    branch_id UUID NOT NULL,
    lease_id UUID NOT NULL REFERENCES rent.leases(id) ON DELETE CASCADE,
    tenant_id UUID NOT NULL REFERENCES rent.tenants(id) ON DELETE CASCADE,
    type VARCHAR(32) NOT NULL, -- rent, penalty, fine, utility
    period VARCHAR(16) NOT NULL, -- например 2026-10
    amount NUMERIC(12,2) NOT NULL,
    due_date DATE NOT NULL,
    is_paid BOOLEAN NOT NULL DEFAULT false,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_rent_charges_lease ON rent.charges(lease_id, period);
CREATE INDEX IF NOT EXISTS idx_rent_charges_tenant ON rent.charges(tenant_id, is_paid);

CREATE TABLE IF NOT EXISTS rent.payments (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    company_id UUID NOT NULL,
    branch_id UUID NOT NULL,
    tenant_id UUID REFERENCES rent.tenants(id) ON DELETE SET NULL,
    amount NUMERIC(12,2) NOT NULL,
    payment_method VARCHAR(64) NOT NULL, -- cash, bank, qr, elcart
    cashier VARCHAR(128) NOT NULL DEFAULT 'Администратор',
    status VARCHAR(32) NOT NULL DEFAULT 'completed', -- completed, storno
    storno_reason TEXT DEFAULT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_rent_payments_comp ON rent.payments(company_id, branch_id);

CREATE TABLE IF NOT EXISTS rent.payment_allocations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    payment_id UUID NOT NULL REFERENCES rent.payments(id) ON DELETE CASCADE,
    charge_id UUID NOT NULL REFERENCES rent.charges(id) ON DELETE CASCADE,
    allocated_amount NUMERIC(12,2) NOT NULL
);

CREATE TABLE IF NOT EXISTS rent.receipts (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    company_id UUID NOT NULL,
    branch_id UUID NOT NULL,
    payment_id UUID NOT NULL REFERENCES rent.payments(id) ON DELETE CASCADE,
    receipt_number VARCHAR(64) NOT NULL,
    snapshot JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS rent.reconciliation_acts (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    company_id UUID NOT NULL,
    branch_id UUID NOT NULL,
    tenant_id UUID NOT NULL REFERENCES rent.tenants(id) ON DELETE CASCADE,
    act_number VARCHAR(64) NOT NULL,
    period_from DATE NOT NULL,
    period_to DATE NOT NULL,
    opening_balance NUMERIC(12,2) NOT NULL DEFAULT 0,
    closing_balance NUMERIC(12,2) NOT NULL DEFAULT 0,
    total_debit NUMERIC(12,2) NOT NULL DEFAULT 0,
    total_credit NUMERIC(12,2) NOT NULL DEFAULT 0,
    rows_json JSONB NOT NULL DEFAULT '[]',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_rent_recon_tenant ON rent.reconciliation_acts(tenant_id);

CREATE TABLE IF NOT EXISTS rent.remarks (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    company_id UUID NOT NULL,
    branch_id UUID NOT NULL,
    tenant_id UUID NOT NULL REFERENCES rent.tenants(id) ON DELETE CASCADE,
    type VARCHAR(32) NOT NULL, -- remark, warning, reprimand, fine
    remark_date DATE NOT NULL,
    text TEXT NOT NULL,
    officer VARCHAR(128) NOT NULL,
    penalty_amount NUMERIC(12,2) DEFAULT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS rent.assets (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    company_id UUID NOT NULL,
    branch_id UUID NOT NULL,
    name VARCHAR(255) NOT NULL,
    cost NUMERIC(12,2) NOT NULL,
    purchase_date DATE NOT NULL,
    useful_life_years INTEGER NOT NULL DEFAULT 5,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Grant permissions to microservice roles
GRANT ALL ON SCHEMA bath TO svc_bath;
GRANT ALL ON ALL TABLES IN SCHEMA bath TO svc_bath;
GRANT ALL ON ALL SEQUENCES IN SCHEMA bath TO svc_bath;

GRANT ALL ON SCHEMA rent TO svc_rent;
GRANT ALL ON ALL TABLES IN SCHEMA rent TO svc_rent;
GRANT ALL ON ALL SEQUENCES IN SCHEMA rent TO svc_rent;
