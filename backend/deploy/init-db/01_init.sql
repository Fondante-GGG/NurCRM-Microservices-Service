-- NurCRM PostgreSQL Database Initialization
-- Single database with strict logical schema separation

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "btree_gist";

-- 1. Create Schemas
CREATE SCHEMA IF NOT EXISTS auth;
CREATE SCHEMA IF NOT EXISTS catalog;
CREATE SCHEMA IF NOT EXISTS clients;
CREATE SCHEMA IF NOT EXISTS schedule;
CREATE SCHEMA IF NOT EXISTS booking;
CREATE SCHEMA IF NOT EXISTS finance;
CREATE SCHEMA IF NOT EXISTS analytics;
CREATE SCHEMA IF NOT EXISTS notify;
CREATE SCHEMA IF NOT EXISTS admin;

-- 2. Create Roles for Microservices
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'svc_auth') THEN
        CREATE ROLE svc_auth WITH LOGIN PASSWORD 'svc_auth_secret';
    END IF;
    IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'svc_catalog') THEN
        CREATE ROLE svc_catalog WITH LOGIN PASSWORD 'svc_catalog_secret';
    END IF;
    IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'svc_clients') THEN
        CREATE ROLE svc_clients WITH LOGIN PASSWORD 'svc_clients_secret';
    END IF;
    IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'svc_schedule') THEN
        CREATE ROLE svc_schedule WITH LOGIN PASSWORD 'svc_schedule_secret';
    END IF;
    IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'svc_booking') THEN
        CREATE ROLE svc_booking WITH LOGIN PASSWORD 'svc_booking_secret';
    END IF;
    IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'svc_finance') THEN
        CREATE ROLE svc_finance WITH LOGIN PASSWORD 'svc_finance_secret';
    END IF;
    IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'svc_analytics') THEN
        CREATE ROLE svc_analytics WITH LOGIN PASSWORD 'svc_analytics_secret';
    END IF;
    IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'svc_notify') THEN
        CREATE ROLE svc_notify WITH LOGIN PASSWORD 'svc_notify_secret';
    END IF;
    IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'svc_admin') THEN
        CREATE ROLE svc_admin WITH LOGIN PASSWORD 'svc_admin_secret';
    END IF;
END
$$;

-- Grant schema permissions
GRANT USAGE, CREATE ON SCHEMA auth TO svc_auth;
GRANT USAGE, CREATE ON SCHEMA catalog TO svc_catalog;
GRANT USAGE, CREATE ON SCHEMA clients TO svc_clients;
GRANT USAGE, CREATE ON SCHEMA schedule TO svc_schedule;
GRANT USAGE, CREATE ON SCHEMA booking TO svc_booking;
GRANT USAGE, CREATE ON SCHEMA finance TO svc_finance;
GRANT USAGE, CREATE ON SCHEMA analytics TO svc_analytics;
GRANT USAGE, CREATE ON SCHEMA notify TO svc_notify;
GRANT USAGE, CREATE ON SCHEMA admin TO svc_admin;

-- Admin panel has read-only access to business schemas, and write access to admin schema
GRANT USAGE ON SCHEMA auth, catalog, clients, schedule, booking, finance TO svc_admin;

-- Set search_paths
ALTER ROLE svc_auth SET search_path = auth, public;
ALTER ROLE svc_catalog SET search_path = catalog, public;
ALTER ROLE svc_clients SET search_path = clients, public;
ALTER ROLE svc_schedule SET search_path = schedule, public;
ALTER ROLE svc_booking SET search_path = booking, public;
ALTER ROLE svc_finance SET search_path = finance, public;
ALTER ROLE svc_analytics SET search_path = analytics, public;
ALTER ROLE svc_notify SET search_path = notify, public;
ALTER ROLE svc_admin SET search_path = admin, public;

---------------------------------------------------------
-- Helper Outbox and Inbox tables in each schema
---------------------------------------------------------
DO $$
DECLARE
    s TEXT;
BEGIN
    FOR s IN SELECT unnest(ARRAY['auth', 'catalog', 'clients', 'schedule', 'booking', 'finance', 'analytics', 'notify']) LOOP
        EXECUTE format('
            CREATE TABLE IF NOT EXISTS %I.outbox (
                id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
                event_id UUID NOT NULL,
                event_type VARCHAR(255) NOT NULL,
                payload JSONB NOT NULL,
                status VARCHAR(32) NOT NULL DEFAULT ''pending'',
                retry_count INT NOT NULL DEFAULT 0,
                error TEXT,
                created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                published_at TIMESTAMPTZ
            );
            CREATE INDEX IF NOT EXISTS idx_%s_outbox_pending ON %I.outbox(status) WHERE status = ''pending'';

            CREATE TABLE IF NOT EXISTS %I.inbox (
                event_id UUID PRIMARY KEY,
                event_type VARCHAR(255) NOT NULL,
                processed_at TIMESTAMPTZ NOT NULL DEFAULT now()
            );
        ', s, s, s, s);
    END LOOP;
END
$$;

---------------------------------------------------------
-- SCHEMA: auth
---------------------------------------------------------
CREATE TABLE IF NOT EXISTS auth.companies (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(255) NOT NULL,
    slug VARCHAR(128) NOT NULL UNIQUE,
    industry VARCHAR(128) NOT NULL DEFAULT 'Услуги',
    sector VARCHAR(128) NOT NULL DEFAULT 'Услуги',
    appointment_work_start TIME NOT NULL DEFAULT '09:00:00',
    appointment_work_end TIME NOT NULL DEFAULT '21:00:00',
    subscription_plan VARCHAR(64) NOT NULL DEFAULT 'Стандарт',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_companies_slug ON auth.companies(slug);

CREATE TABLE IF NOT EXISTS auth.employees (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    company_id UUID NOT NULL,
    first_name VARCHAR(128) NOT NULL,
    last_name VARCHAR(128) NOT NULL,
    email VARCHAR(255) NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    phone_number VARCHAR(32) NOT NULL,
    role VARCHAR(32) NOT NULL DEFAULT 'master',
    role_display VARCHAR(128) NOT NULL DEFAULT 'Специалист',
    avatar VARCHAR(512),
    branch_ids UUID[] DEFAULT '{}',
    is_active BOOLEAN NOT NULL DEFAULT true,
    version INT NOT NULL DEFAULT 1,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_company_email UNIQUE (company_id, email)
);
CREATE INDEX IF NOT EXISTS idx_employees_company_id ON auth.employees(company_id);

CREATE TABLE IF NOT EXISTS auth.sessions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    company_id UUID NOT NULL,
    user_id UUID NOT NULL,
    device VARCHAR(255),
    ip_address VARCHAR(45),
    refresh_token_hash VARCHAR(255) NOT NULL,
    is_revoked BOOLEAN NOT NULL DEFAULT false,
    last_seen TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_sessions_user ON auth.sessions(company_id, user_id);

---------------------------------------------------------
-- SCHEMA: catalog
---------------------------------------------------------
CREATE TABLE IF NOT EXISTS catalog.service_categories (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    company_id UUID NOT NULL,
    name VARCHAR(255) NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT true,
    version INT NOT NULL DEFAULT 1,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_service_categories_comp ON catalog.service_categories(company_id);

CREATE TABLE IF NOT EXISTS catalog.services (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    company_id UUID NOT NULL,
    category_id UUID NOT NULL,
    name VARCHAR(255) NOT NULL,
    price NUMERIC(12,2) NOT NULL DEFAULT 0.00,
    time_minutes INT NOT NULL DEFAULT 30,
    barbers UUID[] DEFAULT '{}',
    is_active BOOLEAN NOT NULL DEFAULT true,
    version INT NOT NULL DEFAULT 1,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_services_comp ON catalog.services(company_id);

CREATE TABLE IF NOT EXISTS catalog.salary_rates (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    company_id UUID NOT NULL,
    service_id UUID NOT NULL,
    master_id UUID,
    percent NUMERIC(5,2) NOT NULL DEFAULT 0.00,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_rate_service_master UNIQUE (company_id, service_id, master_id)
);
CREATE INDEX IF NOT EXISTS idx_rates_company_service ON catalog.salary_rates(company_id, service_id);

---------------------------------------------------------
-- SCHEMA: clients
---------------------------------------------------------
CREATE TABLE IF NOT EXISTS clients.clients (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    company_id UUID NOT NULL,
    full_name VARCHAR(255) NOT NULL,
    phone VARCHAR(32) NOT NULL,
    birth_date DATE,
    status VARCHAR(32) NOT NULL DEFAULT 'active',
    notes TEXT,
    version INT NOT NULL DEFAULT 1,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_client_comp_phone UNIQUE (company_id, phone)
);
CREATE INDEX IF NOT EXISTS idx_clients_comp_phone ON clients.clients(company_id, phone);

CREATE TABLE IF NOT EXISTS clients.client_documents (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    company_id UUID NOT NULL,
    client_id UUID NOT NULL,
    file_path VARCHAR(512) NOT NULL,
    file_name VARCHAR(255) NOT NULL,
    file_size INT NOT NULL,
    file_comment TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_client_docs_client ON clients.client_documents(company_id, client_id);

---------------------------------------------------------
-- SCHEMA: schedule
---------------------------------------------------------
CREATE TABLE IF NOT EXISTS schedule.appointments (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    company_id UUID NOT NULL,
    client_id UUID,
    client_name VARCHAR(255) NOT NULL,
    barber_id UUID NOT NULL,
    services_snapshot JSONB NOT NULL DEFAULT '[]',
    start_at TIMESTAMPTZ NOT NULL,
    end_at TIMESTAMPTZ NOT NULL,
    price NUMERIC(12,2) NOT NULL DEFAULT 0.00,
    discount NUMERIC(12,2) NOT NULL DEFAULT 0.00,
    status VARCHAR(32) NOT NULL DEFAULT 'booked',
    comment TEXT,
    version INT NOT NULL DEFAULT 1,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT no_overlap EXCLUDE USING gist (
        barber_id WITH =,
        tstzrange(start_at, end_at) WITH &&
    ) WHERE (status IN ('booked', 'confirmed', 'completed'))
);
CREATE INDEX IF NOT EXISTS idx_appts_company_date ON schedule.appointments(company_id, start_at);
CREATE INDEX IF NOT EXISTS idx_appts_barber_date ON schedule.appointments(company_id, barber_id, start_at);

CREATE TABLE IF NOT EXISTS schedule.master_schedules (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    company_id UUID NOT NULL,
    master_id UUID NOT NULL,
    day_of_week INT NOT NULL, -- 0 Sunday to 6 Saturday or 1 Monday to 7 Sunday
    start_time TIME NOT NULL DEFAULT '09:00:00',
    end_time TIME NOT NULL DEFAULT '21:00:00',
    is_working BOOLEAN NOT NULL DEFAULT true,
    CONSTRAINT uq_master_day UNIQUE (company_id, master_id, day_of_week)
);

---------------------------------------------------------
-- SCHEMA: booking
---------------------------------------------------------
CREATE TABLE IF NOT EXISTS booking.booking_requests (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    company_id UUID NOT NULL,
    client_name VARCHAR(255) NOT NULL,
    client_phone VARCHAR(32) NOT NULL,
    services JSONB NOT NULL DEFAULT '[]',
    master_id UUID,
    date DATE NOT NULL,
    time_start TIME NOT NULL,
    time_end TIME NOT NULL,
    total_price NUMERIC(12,2) NOT NULL DEFAULT 0.00,
    total_duration_min INT NOT NULL DEFAULT 30,
    payment_method VARCHAR(32) NOT NULL DEFAULT 'cash',
    client_comment TEXT,
    status VARCHAR(32) NOT NULL DEFAULT 'new',
    appointment_id UUID,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_bookings_comp_status ON booking.booking_requests(company_id, status);

---------------------------------------------------------
-- SCHEMA: finance
---------------------------------------------------------
CREATE TABLE IF NOT EXISTS finance.accruals (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    company_id UUID NOT NULL,
    appointment_id UUID NOT NULL UNIQUE,
    master_id UUID NOT NULL,
    service_id UUID,
    amount NUMERIC(12,2) NOT NULL DEFAULT 0.00,
    percent NUMERIC(5,2) NOT NULL DEFAULT 0.00,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_accruals_master ON finance.accruals(company_id, master_id);

CREATE TABLE IF NOT EXISTS finance.salary_payouts (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    company_id UUID NOT NULL,
    master_id UUID NOT NULL,
    amount NUMERIC(12,2) NOT NULL DEFAULT 0.00,
    date DATE NOT NULL DEFAULT CURRENT_DATE,
    cashbox VARCHAR(64) NOT NULL DEFAULT 'Основная касса',
    comment TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_payouts_master ON finance.salary_payouts(company_id, master_id);

CREATE TABLE IF NOT EXISTS finance.cash_shifts (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    company_id UUID NOT NULL,
    user_id UUID NOT NULL,
    cashbox VARCHAR(64) NOT NULL DEFAULT 'Основная касса',
    opening_cash NUMERIC(12,2) NOT NULL DEFAULT 0.00,
    closing_cash NUMERIC(12,2),
    sales_total NUMERIC(12,2) NOT NULL DEFAULT 0.00,
    sales_count INT NOT NULL DEFAULT 0,
    status VARCHAR(32) NOT NULL DEFAULT 'open',
    opened_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    closed_at TIMESTAMPTZ
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_open_shift_per_box ON finance.cash_shifts(company_id, cashbox) WHERE (status = 'open');

CREATE TABLE IF NOT EXISTS finance.warehouse_materials (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    company_id UUID NOT NULL,
    name VARCHAR(255) NOT NULL,
    unit VARCHAR(32) NOT NULL DEFAULT 'шт',
    current_stock NUMERIC(12,3) NOT NULL DEFAULT 0.000,
    cost_price NUMERIC(12,2) NOT NULL DEFAULT 0.00,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS finance.inventory_movements (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    company_id UUID NOT NULL,
    material_id UUID NOT NULL,
    movement_type VARCHAR(32) NOT NULL, -- incoming, write_off, sale
    quantity NUMERIC(12,3) NOT NULL,
    price NUMERIC(12,2) NOT NULL DEFAULT 0.00,
    reason TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

---------------------------------------------------------
-- SCHEMA: analytics
---------------------------------------------------------
CREATE TABLE IF NOT EXISTS analytics.daily_metrics (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    company_id UUID NOT NULL,
    date DATE NOT NULL,
    total_revenue NUMERIC(12,2) NOT NULL DEFAULT 0.00,
    total_appointments INT NOT NULL DEFAULT 0,
    completed_appointments INT NOT NULL DEFAULT 0,
    canceled_appointments INT NOT NULL DEFAULT 0,
    no_show_appointments INT NOT NULL DEFAULT 0,
    avg_check NUMERIC(12,2) NOT NULL DEFAULT 0.00,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_daily_metrics_comp_date UNIQUE (company_id, date)
);

---------------------------------------------------------
-- SCHEMA: notify
---------------------------------------------------------
CREATE TABLE IF NOT EXISTS notify.notifications (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    company_id UUID NOT NULL,
    channel VARCHAR(32) NOT NULL, -- sms, whatsapp
    recipient VARCHAR(64) NOT NULL,
    title VARCHAR(255),
    body TEXT NOT NULL,
    status VARCHAR(32) NOT NULL DEFAULT 'sent', -- pending, sent, failed
    sent_at TIMESTAMPTZ DEFAULT now(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS notify.scheduled_reminders (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    company_id UUID NOT NULL,
    appointment_id UUID NOT NULL,
    reminder_type VARCHAR(32) NOT NULL, -- 24h, 2h
    remind_at TIMESTAMPTZ NOT NULL,
    is_sent BOOLEAN NOT NULL DEFAULT false,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_reminders_pending ON notify.scheduled_reminders(remind_at) WHERE (is_sent = false);

---------------------------------------------------------
-- SCHEMA: admin
---------------------------------------------------------
CREATE TABLE IF NOT EXISTS admin.audit_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    actor_id UUID,
    company_id UUID,
    service VARCHAR(64) NOT NULL,
    action VARCHAR(64) NOT NULL,
    entity_type VARCHAR(64) NOT NULL,
    entity_id UUID,
    before_state JSONB,
    after_state JSONB,
    ip_address VARCHAR(45),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_audit_created ON admin.audit_logs(created_at DESC);

-- Grants on all tables to service roles
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA auth TO svc_auth;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA catalog TO svc_catalog;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA clients TO svc_clients;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA schedule TO svc_schedule;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA booking TO svc_booking;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA finance TO svc_finance;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA analytics TO svc_analytics;
GRANT USAGE ON SCHEMA schedule, finance, auth, catalog, clients TO svc_analytics;
GRANT SELECT ON ALL TABLES IN SCHEMA schedule, finance, auth, catalog, clients TO svc_analytics;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA notify TO svc_notify;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA admin TO svc_admin;
GRANT SELECT ON ALL TABLES IN SCHEMA auth, catalog, clients, schedule, booking, finance TO svc_admin;
