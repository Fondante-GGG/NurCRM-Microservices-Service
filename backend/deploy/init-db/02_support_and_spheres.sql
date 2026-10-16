-- Migration 02: Support, Spheres, Intake modes, Branches, and Shift status
-- Supporting TZ tz-beka-support-i-sfery.md

-- 1. Extend auth.companies
ALTER TABLE auth.companies 
    ADD COLUMN IF NOT EXISTS intake VARCHAR(32) NOT NULL DEFAULT 'schedule',
    ADD COLUMN IF NOT EXISTS legal_name VARCHAR(255) NOT NULL DEFAULT '',
    ADD COLUMN IF NOT EXISTS inn VARCHAR(32) NOT NULL DEFAULT '',
    ADD COLUMN IF NOT EXISTS okpo VARCHAR(32) NOT NULL DEFAULT '',
    ADD COLUMN IF NOT EXISTS account VARCHAR(64) NOT NULL DEFAULT '',
    ADD COLUMN IF NOT EXISTS bik VARCHAR(32) NOT NULL DEFAULT '',
    ADD COLUMN IF NOT EXISTS address TEXT NOT NULL DEFAULT '',
    ADD COLUMN IF NOT EXISTS phones JSONB NOT NULL DEFAULT '[]',
    ADD COLUMN IF NOT EXISTS blocked BOOLEAN NOT NULL DEFAULT false,
    ADD COLUMN IF NOT EXISTS plan VARCHAR(32) NOT NULL DEFAULT 'free',
    ADD COLUMN IF NOT EXISTS temp_access_until TIMESTAMPTZ DEFAULT NULL;

-- Make industry nullable for new accounts (empty initially)
ALTER TABLE auth.companies ALTER COLUMN industry DROP NOT NULL;
ALTER TABLE auth.companies ALTER COLUMN industry DROP DEFAULT;

-- 2. Create auth.branches
CREATE TABLE IF NOT EXISTS auth.branches (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    company_id UUID NOT NULL,
    name VARCHAR(255) NOT NULL,
    address TEXT NOT NULL DEFAULT '',
    is_active BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_branches_comp ON auth.branches(company_id);

-- 3. Create auth.support_tickets
CREATE TABLE IF NOT EXISTS auth.support_tickets (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    company_id UUID NOT NULL,
    topic VARCHAR(64) NOT NULL,
    message TEXT NOT NULL,
    contact VARCHAR(64) NOT NULL,
    share_access BOOLEAN NOT NULL DEFAULT false,
    status VARCHAR(32) NOT NULL DEFAULT 'new',
    assignee VARCHAR(255) NOT NULL DEFAULT '',
    reply TEXT NOT NULL DEFAULT '',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_support_tickets_comp ON auth.support_tickets(company_id);
CREATE INDEX IF NOT EXISTS idx_support_tickets_status ON auth.support_tickets(status);

-- 4. Create auth.support_log
CREATE TABLE IF NOT EXISTS auth.support_log (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    at TIMESTAMPTZ NOT NULL DEFAULT now(),
    agent VARCHAR(255) NOT NULL,
    company_id UUID NOT NULL,
    action TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_support_log_comp ON auth.support_log(company_id);

-- 5. Extend schedule.appointments for flow intake
ALTER TABLE schedule.appointments ALTER COLUMN barber_id DROP NOT NULL;

-- 6. Create schedule.master_shifts with fact = 'planned' | 'worked' | 'missed' | 'busy'
CREATE TABLE IF NOT EXISTS schedule.master_shifts (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    company_id UUID NOT NULL,
    master_id UUID NOT NULL,
    date DATE NOT NULL,
    fact VARCHAR(32) NOT NULL DEFAULT 'planned',
    start_time TIME NOT NULL DEFAULT '09:00:00',
    end_time TIME NOT NULL DEFAULT '21:00:00',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_master_shifts_comp_date ON schedule.master_shifts(company_id, date);
CREATE INDEX IF NOT EXISTS idx_master_shifts_master ON schedule.master_shifts(company_id, master_id, date);

-- Permissions for svc_auth and svc_schedule
GRANT ALL ON auth.branches TO svc_auth;
GRANT ALL ON auth.support_tickets TO svc_auth;
GRANT ALL ON auth.support_log TO svc_auth;
GRANT ALL ON schedule.master_shifts TO svc_schedule;
GRANT USAGE ON SCHEMA catalog TO svc_auth;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA catalog TO svc_auth;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA catalog TO svc_auth;
