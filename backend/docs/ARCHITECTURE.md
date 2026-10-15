# NurCRM Services Backend: Архитектура и спецификация

## 1. Обзор архитектуры

Архитектура бэкенда NurCRM для сферы услуг построена в виде набора микросервисов, объединенных в монорепозиторий (`monorepo`). Каждый сервис реализует методологию **Clean Architecture (Чистая архитектура) + DDD (Domain-Driven Design)** со строгим разграничением слоев:
- **`domain`**: Чистые доменные сущности, Value Objects (`Money`, `Phone`, `TimeSlot`), доменные события, инварианты, интерфейсы репозиториев. Не имеет внешних зависимостей.
- **`application`**: Сценарии использования (Use Cases), команды и запросы, DTO, интерфейсы Unit of Work и порты клиентов.
- **`infrastructure`**: Репозитории (Django ORM, raw SQL), реализация Unit of Work, Transactional Outbox, хранилище файлов на диске, внешние HTTP-клиенты, Redis.
- **`interface`**: Эндпоинты API (DRF Views, FastAPI routers, Go HTTP handlers), сериализаторы, мапперы.

---

## 2. Логическое разделение БД (Single DB with Schema Isolation)

Все сервисы подключены к единой СУБД PostgreSQL 16, но с категорическим разделением по логическим схемам и ролям доступа:
1. `auth` (роль `svc_auth`) — `companies`, `employees`, `sessions`, `outbox`, `inbox`
2. `catalog` (роль `svc_catalog`) — `service_categories`, `services`, `salary_rates`, `outbox`, `inbox`
3. `clients` (роль `svc_clients`) — `clients`, `client_documents`, `outbox`, `inbox`
4. `schedule` (роль `svc_schedule`) — `appointments`, `master_schedules`, `outbox`, `inbox`
5. `booking` (роль `svc_booking`) — `booking_requests`, `outbox`, `inbox`
6. `finance` (роль `svc_finance`) — `accruals`, `salary_payouts`, `cash_shifts`, `warehouse_materials`, `inventory_movements`, `outbox`, `inbox`
7. `analytics` (роль `svc_analytics`) — витрины и агрегаты `daily_metrics`, `outbox`, `inbox`
8. `notify` (роль `svc_notify`) — `notifications`, `scheduled_reminders`, `outbox`, `inbox`
9. `admin` (роль `svc_admin`) — `audit_logs` и доступ на чтение для поддержки

### Правила изоляции:
- **Никаких JOIN и Foreign Key между схемами**: связи хранятся строго через `UUID` (`client_id`, `barber_id`, `service_id`).
- Каждая таблица содержит `company_id UUID NOT NULL` с индексацией (Multi-tenancy).
- На уровне СУБД в таблице `schedule.appointments` настроен GiST-индекс исключения пересечений:
```sql
ALTER TABLE schedule.appointments ADD CONSTRAINT no_overlap
EXCLUDE USING gist (barber_id WITH =, tstzrange(start_at, end_at) WITH &&)
WHERE (status IN ('booked','confirmed','completed'));
```
- Деньги хранятся в типе `NUMERIC(12,2)` в сомах (KGS), время в UTC (`timestamptz`).

---

## 3. Реестр сервисов

| Сервис | Стек | Роль и ответственность |
| :--- | :--- | :--- |
| **auth-service** | DRF + PyJWT (RS256) | Компании, сотрудники, сессии, роли и права, JWKS (`/.well-known/jwks.json`) |
| **catalog-service** | DRF | Категории услуг, услуги, процентные ставки мастеров |
| **client-service** | DRF | Клиентская база, безопасное файловое хранилище документов (`/var/lib/crm/media/clients/...`), история визитов |
| **schedule-service** | DRF | Расписание, журнал визитов, контроль пересечений, жизненный цикл записей, занятые интервалы |
| **booking-service** | DRF | Прием заявок, оркестрация Саги подтверждения (клиент + запись) |
| **finance-service** | DRF | Сдельная зарплата (начисления, выплаты, баланс), кассовые смены, склад расходников |
| **analytics-service** | FastAPI | Высокопроизводительные аналитические отчеты, дашборд, конверсия, рейтинги |
| **notification-service** | FastAPI + Worker | Отправка нотификаций (WhatsApp/SMS), напоминания за 24 часа и за 2 часа |
| **admin-panel** | Django Admin | Панель управления поддержкой с несколькими алиасами БД, аудит-логом и защитой критичных данных |
| **public-gateway** | Go | Публичный виджет записи, быстрый кэш в Redis, движок доступности (Availability Engine) |
| **scheduler-worker** | Go | Фоновый процесс с `pg_advisory_lock`, раз в 60 сек завершает истекшие визиты через internal API |
| **realtime-gateway** | Go | WebSocket (`/ws`) и SSE (`/sse`) сервер мгновенного оповещения о событиях с фильтрацией прав и мягкими блокировками |

---

## 4. Саги и согласованность

### Сага 1: Подтверждение онлайн-заявки (`booking-service`)
1. Администратор переводит заявку в `confirmed` (`PATCH /api/v1/bookings/{id}/`).
2. `booking-service` вызывает `client-service` (`POST /internal/v1/clients/find-or-create/`).
3. `booking-service` вызывает `schedule-service` (`POST /internal/v1/appointments/`) с заголовком `Idempotency-Key: {booking_id}`.
4. Если слот свободен — запись создается, заявка получает `confirmed`, публикуется `booking.request.confirmed`.
5. Если слот занят (ответ 409 `slot_busy`) — заявка остается в статусе `new`, возвращается ошибка 409 с пояснением.

### Сага 2: Автозавершение визитов и сдельная оплата
1. `scheduler-worker` раз в 60 сек получает `pg_try_advisory_lock(987654321)` и вызывает `POST /internal/v1/appointments/auto-complete/`.
2. `schedule-service` переводит визиты с наступившим временем окончания в `completed` и записывает события `schedule.appointment.completed` в `schedule.outbox`.
3. `finance-service` получает событие, запрашивает процент мастера у `catalog-service` и начисляет:
   $$\text{Начисление} = \text{Цена} \times \left(\frac{\text{Процент ставки}}{100}\right)$$
4. Благодаря уникальности поля `appointment_id` в таблице `finance.accruals`, повторные события исключают дублирование зарплаты.

---

## 5. Защита от конфликтов при одновременной работе

1. **Оптимистичная блокировка**: все изменяемые агрегаты имеют поле `version`. При изменении клиент передает `If-Match: <version>`. При расхождении сервер возвращает `409 version_conflict`.
2. **Мягкие блокировки (Soft Locks)**: при начале редактирования карточки клиентом через WebSocket в Redis выставляется ключ `edit:{entity}:{id}` на 60 секунд («Айгуль сейчас правит эту запись»).
3. **Уникальность клиентов**: уникальный индекс `(company_id, phone)` исключает дублирование клиентов в базе.
4. **Кассовые смены**: частичный уникальный индекс `CREATE UNIQUE INDEX ... WHERE (status = 'open')` гарантирует только одну открытую смену на кассу.
