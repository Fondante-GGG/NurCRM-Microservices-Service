-- Migration 03: Seed Stage Data according to Section 6 of tz-beka-support-i-sfery.md

-- 1. Company "NurCRM Support Platform" (for support staff)
INSERT INTO auth.companies (
    id, name, slug, industry, sector, intake, subscription_plan, plan
) VALUES (
    '00000000-0000-0000-0000-000000000000',
    'NurCRM Platform Support',
    'nurcrm-support',
    'barber',
    'Услуги',
    'schedule',
    'Платформа',
    'paid'
) ON CONFLICT (id) DO NOTHING;

-- Support user: support@nurcrm.kg (password: Password123!)
INSERT INTO auth.employees (
    id, company_id, first_name, last_name, email, password_hash, phone_number, role, role_display, is_active
) VALUES (
    '00000000-0000-0000-0000-000000000001',
    '00000000-0000-0000-0000-000000000000',
    'Алишер',
    'Поддержка',
    'support@nurcrm.kg',
    '56d2fb40de3405fae833caa1de0cb8631ad8222fe0b2515f06dc63a17944c457',
    '+996777000111',
    'support',
    'Техподдержка NurCRM',
    true
) ON CONFLICT (id) DO NOTHING;


-- 2. Company 1: "Premium" (barber, schedule)
INSERT INTO auth.companies (
    id, name, slug, industry, sector, intake, legal_name, inn, okpo, account, bik, address, phones, subscription_plan, plan
) VALUES (
    '11111111-1111-1111-1111-111111111111',
    'Premium',
    'premium',
    'barber',
    'Услуги',
    'schedule',
    'ОсОО "Премиум Барбершоп"',
    '12345678901234',
    '12345678',
    '1180000123456789',
    '118001',
    'г. Бишкек, пр. Чуй, 120',
    '["+996555112233"]'::jsonb,
    'Бизнес',
    'paid'
) ON CONFLICT (id) DO UPDATE SET
    industry = 'barber',
    intake = 'schedule',
    legal_name = 'ОсОО "Премиум Барбершоп"',
    inn = '12345678901234',
    address = 'г. Бишкек, пр. Чуй, 120',
    phones = '["+996555112233"]'::jsonb;

-- Owner: owner@premium.kg (password: Password123!)
INSERT INTO auth.employees (
    id, company_id, first_name, last_name, email, password_hash, phone_number, role, role_display, is_active
) VALUES (
    '11111111-1111-1111-1111-111111111101',
    '11111111-1111-1111-1111-111111111111',
    'Умар',
    'Премиум',
    'owner@premium.kg',
    '56d2fb40de3405fae833caa1de0cb8631ad8222fe0b2515f06dc63a17944c457',
    '+996555112233',
    'owner',
    'Владелец',
    true
) ON CONFLICT (id) DO NOTHING;

-- Branch: Филиал Чуй
INSERT INTO auth.branches (
    id, company_id, name, address, is_active
) VALUES (
    '11111111-1111-1111-1111-111111111102',
    '11111111-1111-1111-1111-111111111111',
    'Филиал Чуй',
    'г. Бишкек, пр. Чуй, 120',
    true
) ON CONFLICT (id) DO NOTHING;

-- Master: Азамат Барбер
INSERT INTO auth.employees (
    id, company_id, first_name, last_name, email, password_hash, phone_number, role, role_display, is_active, branch_ids
) VALUES (
    '11111111-1111-1111-1111-111111111103',
    '11111111-1111-1111-1111-111111111111',
    'Азамат',
    'Барбер',
    'azamat@premium.kg',
    '56d2fb40de3405fae833caa1de0cb8631ad8222fe0b2515f06dc63a17944c457',
    '+996555998877',
    'master',
    'Топ-барбер',
    true,
    ARRAY['11111111-1111-1111-1111-111111111102'::uuid]
) ON CONFLICT (id) DO NOTHING;

-- Catalog for Premium
INSERT INTO catalog.service_categories (
    id, company_id, name, is_active
) VALUES (
    '11111111-1111-1111-1111-111111111104',
    '11111111-1111-1111-1111-111111111111',
    'Стрижки',
    true
) ON CONFLICT (id) DO NOTHING;

INSERT INTO catalog.services (
    id, company_id, category_id, name, price, time_minutes, is_active
) VALUES (
    '11111111-1111-1111-1111-111111111105',
    '11111111-1111-1111-1111-111111111111',
    '11111111-1111-1111-1111-111111111104',
    'Мужская стрижка',
    800.00,
    45,
    true
) ON CONFLICT (id) DO NOTHING;


-- 3. Company 2: "MedClinic Flow" (procedure, flow)
INSERT INTO auth.companies (
    id, name, slug, industry, sector, intake, legal_name, inn, okpo, account, bik, address, phones, subscription_plan, plan
) VALUES (
    '22222222-2222-2222-2222-222222222222',
    'MedClinic Flow',
    'medclinic-flow',
    'procedure',
    'Услуги',
    'flow',
    'ОсОО "МедКлиник Процедурная"',
    '98765432109876',
    '87654321',
    '1180000987654321',
    '118001',
    'г. Бишкек, ул. Киевская, 45',
    '["+996700112233"]'::jsonb,
    'Бизнес',
    'paid'
) ON CONFLICT (id) DO UPDATE SET
    industry = 'procedure',
    intake = 'flow',
    legal_name = 'ОсОО "МедКлиник Процедурная"',
    inn = '98765432109876',
    address = 'г. Бишкек, ул. Киевская, 45',
    phones = '["+996700112233"]'::jsonb;

-- Owner: owner@medclinic.kg (password: Password123!)
INSERT INTO auth.employees (
    id, company_id, first_name, last_name, email, password_hash, phone_number, role, role_display, is_active
) VALUES (
    '22222222-2222-2222-2222-222222222201',
    '22222222-2222-2222-2222-222222222222',
    'Бектур',
    'Клиника',
    'owner@medclinic.kg',
    '56d2fb40de3405fae833caa1de0cb8631ad8222fe0b2515f06dc63a17944c457',
    '+996700112233',
    'owner',
    'Владелец',
    true
) ON CONFLICT (id) DO NOTHING;

-- Branch: Процедурный кабинет
INSERT INTO auth.branches (
    id, company_id, name, address, is_active
) VALUES (
    '22222222-2222-2222-2222-222222222202',
    '22222222-2222-2222-2222-222222222222',
    'Центральный процедурный кабинет',
    'г. Бишкек, ул. Киевская, 45',
    true
) ON CONFLICT (id) DO NOTHING;

-- Nurse: Айгуль
INSERT INTO auth.employees (
    id, company_id, first_name, last_name, email, password_hash, phone_number, role, role_display, is_active, branch_ids
) VALUES (
    '22222222-2222-2222-2222-222222222203',
    '22222222-2222-2222-2222-222222222222',
    'Айгуль',
    'Медсестра',
    'aigul@medclinic.kg',
    '56d2fb40de3405fae833caa1de0cb8631ad8222fe0b2515f06dc63a17944c457',
    '+996700998877',
    'master',
    'Процедурная медсестра',
    true,
    ARRAY['22222222-2222-2222-2222-222222222202'::uuid]
) ON CONFLICT (id) DO NOTHING;

-- Catalog for MedClinic Flow
INSERT INTO catalog.service_categories (
    id, company_id, name, is_active
) VALUES (
    '22222222-2222-2222-2222-222222222204',
    '22222222-2222-2222-2222-222222222222',
    'Инъекции и капельницы',
    true
) ON CONFLICT (id) DO NOTHING;

INSERT INTO catalog.services (
    id, company_id, category_id, name, price, time_minutes, is_active
) VALUES (
    '22222222-2222-2222-2222-222222222205',
    '22222222-2222-2222-2222-222222222222',
    '22222222-2222-2222-2222-222222222204',
    'Внутривенная капельница',
    500.00,
    40,
    true
) ON CONFLICT (id) DO NOTHING;
