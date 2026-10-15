# ТЗ Backend: CRM для сферы услуг

Версия 1.0 · 15.10.2026 · основа: «ТЗ CRM Services Sphere» (NurCRM)

## 1. Цель и границы

Разработать backend из набора сервисов (DRF, FastAPI, Go) поверх **единого PostgreSQL** с логическим разделением по схемам, чтобы позже любой сервис можно было вынести в отдельную БД без переписывания кода. Для сотрудников поддержки добавляется Django Admin.

Вне границ: frontend, мобильное приложение, онлайн-эквайринг (этап 4 дорожной карты).

## 2. Сервисы

| Сервис | Стек | Ответственность | Схема БД |
| --- | --- | --- | --- |
| auth-service | DRF + SimpleJWT | Company, Employee, роли и права, выпуск JWT, JWKS | `auth` |
| catalog-service | DRF | ServiceCategory, Service, SalaryRate | `catalog` |
| client-service | DRF | Client, ClientDocument (файлы на диске сервера), история визитов | `clients` |
| schedule-service | DRF | Appointment, график мастеров, конфликты, статусы | `schedule` |
| booking-service | DRF | BookingRequest, подтверждение заявки (сага) | `booking` |
| finance-service | DRF | Accrual, Payout, Summary, кассовые смены, склад | `finance` |
| analytics-service | FastAPI | Дашборд, рейтинги, конверсия (только чтение) | `analytics` (витрины) |
| notification-service | FastAPI + worker | WhatsApp/SMS, напоминания за 24ч/2ч | `notify` |
| public-gateway | Go | Публичный API виджета, расчёт слотов (availability) | нет своих таблиц, Redis |
| scheduler-worker | Go | Автозавершение визитов каждые 60 сек | нет своих таблиц |
| admin-panel | Django Admin | Админка для поддержки и владельцев платформы | `admin` |
| realtime-gateway | Go | WebSocket/SSE: мгновенная доставка изменений всем пользователям компании | нет своих таблиц, Redis |

Внешние компоненты: Nginx/Traefik (gateway), RabbitMQ, Redis, общий Docker-том для файлов, PostgreSQL 16.

## 3. Единая БД с готовностью к разделению

### 3.1. Правила (обязательны)

1. **Одна схема на сервис**, у каждого сервиса своя роль БД (`svc_schedule` и т.д.) с правами только на свою схему. Чужие схемы недоступны.
2. **Никаких FK и JOIN между схемами.** Связи с чужими сущностями хранятся как UUID без внешнего ключа (`client_id`, `barber_id`, `service_id`).
3. **Никаких запросов к чужим таблицам.** Данные другого сервиса берутся только через API или события (раздел 5–6).
4. Миграции каждой схемы выполняет только её сервис. Таблица миграций Django лежит в своей схеме.
5. Подключение настраивается переменной `DATABASE_URL` на сервис. Сейчас все указывают на один хост, различается `search_path` и роль.
6. Каждая таблица содержит `company_id` (UUID, NOT NULL, индекс). Составные индексы начинаются с `company_id`.
7. Деньги: `NUMERIC(12,2)`, валюта KGS. Время: `timestamptz`, хранение в UTC.

### 3.2. Техническое

- Row Level Security по `company_id` включается на таблицах `schedule`, `clients`, `finance` как второй рубеж защиты; сервис выполняет `SET app.company_id` на транзакцию.
- В каждой схеме есть таблицы `outbox` (события на отправку) и `inbox` (обработанные события для идемпотентности).
- Защита от двойной брони на уровне БД:

```sql
ALTER TABLE schedule.appointments ADD CONSTRAINT no_overlap
EXCLUDE USING gist (barber_id WITH =, tstzrange(start_at, end_at) WITH &&)
WHERE (status IN ('booked','confirmed','completed'));
```

- Accrual уникален по `appointment_id`: повторное событие не удваивает зарплату.

### 3.3. План выноса сервиса в отдельную БД

1. Создать новый инстанс, перенести схему через `pg_dump -n <schema>` и логическую репликацию.
2. Сменить `DATABASE_URL` сервиса.
3. Сменить DSN алиаса в admin-panel (раздел 4).
4. Удалить схему из общей БД после проверки.

Правила 1–3 гарантируют, что код сервиса при этом не меняется.

## 4. Django Admin (admin-panel)

- Отдельный Django-проект, не часть бизнес-сервисов. Доступ только из внутренней сети/VPN, обязательная 2FA, отдельный домен.
- **Несколько алиасов БД**: `auth`, `catalog`, `clients`, `schedule`, `booking`, `finance`. Каждый алиас имеет свой `search_path` и роль. Сейчас DSN совпадают, при разделении меняется только DSN.
- `DATABASE_ROUTERS` направляет модель на алиас по `app_label`.
- Модели в admin-panel зеркальные, `managed = False`. Генерируются командой `inspectdb`, в CI контрактный тест падает при расхождении со схемой сервиса.
- Правила редактирования:
  - справочники (Company, Service, ServiceCategory, Client, Employee): чтение и правка;
  - критичные данные (Appointment, Accrual, Payout, Shift): **только чтение**; изменения через admin-actions, которые вызывают внутренний API сервиса-владельца, чтобы не обходить бизнес-правила и события;
  - пароли и токены в админке не отображаются.
- Роли админки: `superadmin`, `support` (клиенты, справочники, просмотр записей), `finance_viewer` (только чтение finance).
- Все действия пишутся в `admin.audit_log` (кто, что, до/после, IP).

## 5. Синхронное взаимодействие

Протокол: **REST/JSON** по внутренней сети, префикс `/internal/v1/`, не публикуется наружу через gateway. Контракты в OpenAPI, у каждого сервиса клиентская обёртка с таймаутом 2 сек, 2 ретрая с backoff, circuit breaker.

Аутентификация между сервисами: JWT по схеме client credentials (`aud` = сервис-получатель, `sub` = сервис-отправитель, TTL 5 мин).

| Вызов | Откуда → куда | Зачем |
| --- | --- | --- |
| Список услуг и длительностей по ID | schedule → catalog | Расчёт `end_at` и цены |
| Допуск мастера к услуге | schedule → catalog | Валидация записи |
| Найти/создать клиента по телефону | booking → client | Подтверждение заявки |
| Создать запись | booking → schedule | Подтверждение заявки |
| Занятые интервалы мастера на дату | public-gateway → schedule | Fallback при промахе кэша |
| Создать заявку | public-gateway → booking | Публичная онлайн-запись |
| Ставка за услугу | finance → catalog | Расчёт начисления |
| Применить действие админа | admin-panel → любой | Изменение критичных данных |

Правило: цепочки синхронных вызовов глубже 2 уровней запрещены, всё остальное через события.

## 6. Асинхронное взаимодействие (события)

**Брокер:** RabbitMQ, topic exchange `crm.events`, routing key `<домен>.<сущность>.<событие>`.

**Transactional Outbox:** сервис пишет бизнес-данные и событие в `outbox` в одной транзакции. Relay-процесс публикует события в брокер и помечает их отправленными. Это исключает потерю событий.

**Inbox:** потребитель сохраняет `event_id` в `inbox`, повторная доставка игнорируется (идемпотентность).

**Формат события (JSON):**

```json
{
  "event_id": "uuid",
  "type": "schedule.appointment.completed",
  "version": 1,
  "occurred_at": "2026-10-15T10:00:00Z",
  "company_id": "uuid",
  "trace_id": "uuid",
  "data": { }
}
```

### Каталог событий

| Событие | Публикует | Подписчики | Действие |
| --- | --- | --- | --- |
| `auth.company.changed` | auth | public-gateway, schedule | Часы работы, slug, обновить кэш |
| `auth.employee.changed` | auth | public-gateway, catalog | Мастера, фото, должности, график |
| `catalog.service.changed` | catalog | public-gateway, finance | Цена, длительность, активность |
| `client.client.created` / `.updated` | client | analytics | Витрина клиентов |
| `schedule.appointment.created` | schedule | public-gateway, notification, analytics | Обновить busy-слоты, письмо клиенту |
| `schedule.appointment.updated` / `.canceled` | schedule | public-gateway, notification, analytics | Освободить слот, уведомить |
| `schedule.appointment.completed` | schedule / scheduler-worker | finance, client, analytics | Начисление, счётчики визитов |
| `booking.request.created` | booking | notification, analytics | Новая заявка администратору |
| `booking.request.confirmed` | booking | analytics | Конверсия заявок |
| `finance.payout.created` | finance | notification, analytics | Витрина зарплат |
| `finance.shift.closed` | finance | analytics | Кассовые отчёты |

Изменение события: обратно совместимые поля добавляются без смены версии, ломающие изменения публикуются как `version: 2` параллельно с `version: 1` на период миграции.

**Очереди:** на каждого потребителя своя durable-очередь, DLQ с 5 ретраями и экспоненциальной паузой.

## 7. Саги и согласованность

### 7.1. Подтверждение онлайн-заявки (оркестрация в booking-service)

1. Администратор вызывает `PATCH /bookings/{id}/` со статусом `confirmed`.
2. booking → client: найти клиента по `company_id` + телефон, иначе создать.
3. booking → schedule: создать запись `confirmed` (заголовок `Idempotency-Key = booking_id`).
4. Если запись создана, заявка получает статус `confirmed`, публикуется `booking.request.confirmed`.
5. Если слот уже занят (ответ 409), заявка остаётся `new`, администратор получает ошибку «слот занят». Созданного клиента откатывать не нужно (он остаётся в базе).

### 7.2. Завершение визита и начисление

1. scheduler-worker выполняет раз в 60 сек (с `pg_advisory_lock`, чтобы не запускалось дважды):

```sql
UPDATE schedule.appointments SET status='completed'
WHERE status IN ('booked','confirmed') AND end_at <= now()
RETURNING id, company_id, barber_id;
```

Worker идёт через internal API schedule-service (`POST /internal/v1/appointments/auto-complete/`), чтобы событие попало в outbox. 2. schedule публикует `appointment.completed`. 3. finance получает событие, запрашивает ставки у catalog (или берёт из локальной копии по `catalog.service.changed`), создаёт Accrual: `цена × процент / 100`. 4. Повторное событие не создаёт дубль (уникальность `appointment_id`).

### 7.3. Правила согласованности

- Между сервисами используется **eventual consistency**, допустимая задержка событий до 5 сек.
- Распределённых транзакций нет.
- Каждая операция записи принимает заголовок `Idempotency-Key`.

## 8. Безопасность

- JWT RS256, Access 15 мин, Refresh 7 дней. Auth публикует ключи на `/.well-known/jwks.json`, остальные сервисы проверяют токен локально.
- Claims: `sub`, `company_id`, `role`, `permissions[]` (`can_view_salary` и др. из раздела 7 исходного ТЗ), `exp`.
- Сервисы доверяют только `company_id` из токена, из тела запроса он никогда не берётся.
- Публичные эндпоинты: rate limit (IP и телефон), honeypot/капча, валидация телефона, лимит размера тела 32 КБ.
- Секреты в переменных окружения / Vault, пароли PBKDF2 или Argon2.
- Файлы клиентов: хранятся на диске сервера в отдельном Docker-томе (/var/lib/crm/media/clients/\<company\_id>/\<client\_id>/), имя файла — UUID; прямого публичного доступа нет, выдача только через client-service с проверкой прав (nginx X-Accel-Redirect), проверка типа и размера (до 10 МБ).
- Персональные данные в логах маскируются (телефон).

## 9. Redis и кэш

| Ключ | Содержимое | Обновление |
| --- | --- | --- |
| `pub:{slug}:services` | Каталог для виджета | TTL 300 сек + инвалидация по `catalog.service.changed` |
| `pub:{slug}:masters` | Мастера, фото, должности | по `auth.employee.changed` |
| `busy:{company}:{master}:{date}` | Занятые интервалы | по событиям `schedule.appointment.*`, TTL 24ч |
| `rl:{ip}` / `rl:{phone}` | Счётчики rate limit | TTL по окну |

При промахе кэша Go-сервис обращается по internal API к владельцу данных и кладёт результат в Redis.

## 10. Правила API

- Версия: `/api/v1/...` (публичные пути из исходного ТЗ сохраняются как алиасы).
- Пагинация: `limit`/`offset`, максимум 100, ответ `{count, results}`.
- Формат ошибки: `{"code": "slot_busy", "message": "...", "details": {}, "trace_id": "..."}`.
- Коды: 400 валидация, 401, 403, 404, 409 конфликт (занят слот, дубль клиента), 429 лимит.
- Даты в ISO 8601 с таймзоной, фильтры `date_from`, `date_to`.
- Документация: OpenAPI из DRF (drf-spectacular), FastAPI и Go (swaggo) публикуются на `/docs`, сборка падает, если схема сломала контракт (проверка oasdiff в CI).

## 11. Нефункциональные требования

| Параметр | Значение |
| --- | --- |
| Публичные GET (кэш) | p95 < 50 мс при 1000 RPS |
| Расчёт слотов | p95 < 150 мс для 10 мастеров |
| Внутренние CRUD | p95 < 300 мс |
| Доступность | 99,5% |
| RPO / RTO БД | 15 мин / 1 час (WAL-архив, ежедневный бэкап) |
| Задержка событий | < 5 сек |
| Покрытие тестами | ≥ 80% бизнес-логики |

Наблюдаемость: структурные JSON-логи с `trace_id` (пробрасывается через заголовок `X-Trace-Id` и поле события), метрики Prometheus (`/metrics`), Grafana-дашборды, алерты на рост DLQ и задержку outbox, Sentry для ошибок.

## 12. Инфраструктура

- Docker-образ на сервис, оркестрация: docker-compose для dev, Kubernetes или Swarm для prod.
- Файлы клиентов лежат в томе `/var/lib/crm/media`, который монтируется только в client-service и входит в ежедневный бэкап вместе с БД. Пока client-service работает в одном экземпляре; для нескольких экземпляров том выносится на общий сетевой диск (NFS), код не меняется.
- Один репозиторий (monorepo): `services/<name>`, `libs/` (общие клиенты, схемы событий), `deploy/`, `docs/`.
- Окружения: dev, stage, prod. CI: линтер, тесты, проверка миграций, сборка образов, контрактные тесты.
- Миграции запускаются отдельным job до выкладки сервиса. Откат только вперёд (expand/contract).

## 13. Этапы и приёмка

| Этап | Состав | Критерий приёмки |
| --- | --- | --- |
| 1 | Инфраструктура, auth, catalog, client, admin-panel | Вход по JWT, CRUD услуг/клиентов, админка читает все схемы |
| 2 | schedule + outbox/inbox + RabbitMQ | Запись без накладок (проверка нагрузочным тестом на гонки) |
| 3 | public-gateway (Go) + booking | Виджет оформляет заявку, подтверждение создаёт клиента и запись |
| 4 | scheduler-worker + finance | Визит завершается автоматически, начисление создаётся ровно один раз |
| 5 | analytics (FastAPI) | Дашборд совпадает с контрольным расчётом по SQL |
| 6 | notification | Уведомление создаётся и напоминание уходит за 2ч |
| 7 | realtime-gateway, оптимистичные блокировки (раздел 15) | Два пользователя одной компании видят изменения друг друга за ≤ 2 сек, одновременное сохранение одного слота даёт ровно один успех |

Общая приёмка: изоляция тенантов проверена тестами (пользователь компании A не видит данные B), разделение схем проверено (роль сервиса не имеет доступа к чужой схеме), вынос одной схемы в отдельную БД на stage выполнен только сменой DSN.

## 14. Архитектура кода сервисов

Каждый сервис (DRF, FastAPI, Go) строится по Clean Architecture с DDD, внедрением зависимостей (DI) и Unit of Work (UoW). Один сервис = один bounded context, бизнес-правила не зависят ни от фреймворка, ни от БД.

### 14.1. Слои (зависимости направлены только внутрь)

| Слой | Что внутри | Может импортировать |
| --- | --- | --- |
| `domain` | Агрегаты, сущности, value objects (Money, Phone, TimeSlot), доменные события, доменные сервисы, интерфейсы репозиториев | ничего внешнего |
| `application` | Use case (команда или запрос), DTO, интерфейсы UoW, EventBus и внешних клиентов | `domain` |
| `infrastructure` | Репозитории (Django ORM, SQLAlchemy, pgx), реализация UoW, outbox, HTTP-клиенты, Redis, файловое хранилище | `domain`, `application` |
| `interface` | DRF views и serializers, FastAPI routers, Go handlers: разбор запроса, вызов use case, формат ответа | `application` |

Композиционный корень (`bootstrap`) собирает зависимости в одном месте и больше нигде.

### 14.2. Структура каталога сервиса

```text
services/schedule/
  domain/          appointment.py, value_objects.py, events.py, repositories.py
  application/     use_cases/create_appointment.py, dto.py, uow.py, ports.py
  infrastructure/  orm/, repositories.py, uow.py, outbox.py, clients/
  interface/       api/ (views, serializers, routers), consumers/
  bootstrap.py     DI-контейнер
  tests/           unit/ (domain, application без БД), integration/, contract/
```

У Go-сервисов те же слои как пакеты: `internal/domain`, `internal/app`, `internal/infra`, `internal/transport`, `cmd/<service>/main.go`.

### 14.3. Агрегаты по сервисам

| Сервис | Агрегаты (корень выделен первым) | Инварианты |
| --- | --- | --- |
| auth | Company; Employee | Уникальный slug, роль из списка |
| catalog | Service (+ допущенные мастера); ServiceCategory; SalaryRate | Процент ставки 0–100, длительность > 0 |
| client | Client (+ ClientDocument) | Телефон уникален в компании |
| schedule | Appointment; MasterSchedule | `end_at` = `start_at` + сумма длительностей, нет пересечений, допустимые переходы статусов |
| booking | BookingRequest | Переход `new` → `confirmed` один раз |
| finance | Accrual; Payout; CashShift | Одно начисление на запись, одна открытая смена на кассу, выплата не больше баланса |

Услуги в Appointment хранятся снимком (название, цена, длительность на момент записи), а не ссылкой на изменяемый справочник.

### 14.4. Unit of Work

- Один use case = одна транзакция БД = один UoW.
- UoW отдаёт репозитории, выполняет `commit` и `rollback`, собирает доменные события из изменённых агрегатов и записывает их в `outbox` в той же транзакции (раздел 6).
- Use case не знает про ORM и не вызывает `save()` напрямую, только `uow.<repo>.add/get` и `uow.commit()`.

```python
class UnitOfWork(Protocol):
    appointments: AppointmentRepository
    def __enter__(self) -> "UnitOfWork": ...
    def __exit__(self, *exc) -> None: ...   # rollback, если не было commit
    def commit(self) -> None: ...           # пишет outbox и фиксирует транзакцию

class CreateAppointment:
    def __init__(self, uow: UnitOfWork, catalog: CatalogClient): ...
    def execute(self, cmd: CreateAppointmentCommand) -> AppointmentDTO:
        with self.uow:
            services = self.catalog.get_services(cmd.company_id, cmd.service_ids)
            appt = Appointment.create(cmd, services)   # правила внутри домена
            self.uow.appointments.add(appt)
            self.uow.commit()
        return AppointmentDTO.from_domain(appt)
```

### 14.5. Dependency Injection

- Python: DRF-сервисы через `dependency-injector`, FastAPI через `Depends` поверх того же контейнера.
- Go: явные конструкторы, сборка через `google/wire` (на этапе компиляции), без глобальных переменных и `init()`.
- Зависимости объявляются как интерфейсы в `domain`/`application`, реализации подставляются в `bootstrap`.
- В тестах репозитории, UoW и клиенты заменяются in-memory заглушками.

### 14.6. Правила, которые проверяет CI

- Python: `import-linter` запрещает импорт `infrastructure` и `interface` из `domain` и `application`. Go: `depguard` с теми же правилами.
- Django ORM-модели лежат только в `infrastructure`; в `domain` чистые классы без Django и SQLAlchemy.
- Serializers DRF и схемы Pydantic только валидируют вход и формируют ответ, бизнес-логики в них нет.
- Чтение (queries) может идти в обход агрегатов прямыми SQL-запросами в `infrastructure` (CQRS-lite), запись только через use case.
- Покрытие `domain` и `application` юнит-тестами без БД не ниже 90%.

## 15. Несколько пользователей одного аккаунта

Несколько сотрудников одной компании (например, два администратора и мастер) работают одновременно, видят изменения друг друга за 2 секунды без перезагрузки страницы и не портят данные друг друга. То же для одного пользователя на нескольких устройствах.

### 15.1. Сессии

- Лимита на число одновременных входов в аккаунт нет. Каждый вход создаёт отдельную сессию `auth.sessions` (id, пользователь, устройство, IP, `last_seen`) со своим refresh-токеном.
- В access-токене лежит claim `sid`. Выход или отзыв одной сессии не затрагивает остальные; владелец может завершить любую сессию сотрудника.
- Все действия пишут `actor_id` и `sid` в аудит и в события.

### 15.2. Защита от конфликтов записи

| Ситуация | Решение | Результат для второго пользователя |
| --- | --- | --- |
| Два админа правят одну запись, клиента или услугу | Оптимистичная блокировка: поле `version`, клиент шлёт `If-Match: <version>`, UoW выполняет `UPDATE ... WHERE id = ? AND version = ?` | 409 `version_conflict` с актуальным состоянием, форма предлагает обновить |
| Два админа создают запись на один слот мастера | Exclusion constraint в БД (раздел 3.2) | 409 `slot_busy` |
| Два админа подтверждают одну онлайн-заявку | Атомарный переход `UPDATE ... WHERE status = 'new'` | 409 `already_processed` с именем того, кто подтвердил |
| Открытие смены кассы двумя админами | Partial unique index: одна открытая смена на кассу | 409 `shift_already_open` |
| Один клиент создан дважды | Unique `(company_id, phone)` | 409 `client_exists` с ссылкой на существующего |
| Автозавершение и ручная смена статуса | Автозавершение трогает только записи в `booked` и `confirmed` и тоже проверяет `version` | Ручное изменение не затирается |
| Повторная отправка формы | Заголовок `Idempotency-Key` | Тот же ответ, дубля нет |

Поле `version` увеличивается на 1 при каждом изменении агрегата и приходит в каждом ответе API и событии.

### 15.3. Синхронизация в реальном времени (realtime-gateway)

1. Браузер открывает WebSocket `/ws` (запасной вариант SSE), первым сообщением отправляет access JWT. Gateway проверяет токен локально по JWKS.
2. Соединение попадает в комнату `company:{company_id}`. Права фильтруют поток: мастер получает только свои записи, финансовые события получают только с `can_view_salary` или `can_view_cashbox`.
3. Gateway подписан на события RabbitMQ (`schedule.*`, `booking.*`, `client.*`, `finance.shift.*`) и рассылает в комнату короткое сообщение:

```json
{"type": "schedule.appointment.updated", "id": "uuid", "version": 7,
 "actor_id": "uuid", "event_seq": 10452, "occurred_at": "2026-10-15T10:00:00Z"}
```

4. Клиент сравнивает `version` с локальной и при отставании запрашивает сущность по REST. Сообщения с собственным `actor_id` и `sid` не перерисовываются.
5. Несколько экземпляров gateway синхронизируются через Redis pub/sub. Журнал последних событий хранится 5 минут в Redis Stream.
6. После обрыва связи клиент отправляет `last_event_seq`. Если разрыв больше 5 минут, он перезагружает данные экрана целиком.
7. Подсказка «Айгуль сейчас правит эту запись»: мягкая блокировка `edit:{entity}:{id}` в Redis на 60 секунд. Она только предупреждает, защита от перезаписи остаётся на `version`.

Доставка: не дольше 2 секунд от `commit` до экрана другого пользователя, 1000 одновременных соединений на экземпляр gateway.

### 15.4. Что остаётся в REST

WebSocket только уведомляет, все изменения идут через обычный REST API сервисов. Это сохраняет единые права, аудит и идемпотентность, а gateway не содержит бизнес-логики.

### 15.5. Критерии приёмки

- Два браузера под разными пользователями одной компании: запись, созданная в первом, появляется во втором не позже чем через 2 секунды.
- Одновременное сохранение одного слота двумя пользователями: один успех, один 409 `slot_busy`.
- Одновременное подтверждение одной заявки: один успех, второй видит, кто подтвердил.
- Правка устаревшей версии записи возвращает 409 и не затирает чужие изменения.
- После разрыва соединения на 30 секунд экран приходит в актуальное состояние без перезагрузки.
- Выход с одного устройства не разлогинивает другие устройства того же пользователя.
