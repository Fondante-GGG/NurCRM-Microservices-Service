# NurCRM Backend — Микросервисная платформа для сферы услуг

Платформа автоматизации бизнеса в сфере услуг (барбершопы, салоны красоты, клиники, спа, сервисные центры) на базе микросервисной архитектуры с изоляцией схем PostgreSQL, DDD/Clean Architecture и высокопроизводительными Go-шлюзами.

---

## 🛠 Технологический стек

- **Языки программирования:** Python 3.11 (DRF, FastAPI, PyJWT, Pydantic v2), Go 1.22 (чистый Go, gorilla/websocket, pgx/pq).
- **База данных:** PostgreSQL 16 с расширениями `uuid-ossp` и `btree_gist` (GiST exclusion constraint `no_overlap`).
- **События и сообщения:** Transactional Outbox / Inbox, RabbitMQ 3, Redis 7 Pub/Sub.
- **Шлюз и оркестрация:** Nginx Gateway (порт 80), Docker Compose (единый запуск 19 контейнеров).
- **Безопасность:** Асимметричные токены JWT (RS256) с автоматической валидацией через JWKS (`/.well-known/jwks.json`).

---

## 🏛 Архитектура сервисов

```
                            [ Клиенты / Виджет онлайн-записи ]
                                            │
                                            ▼
                        [ Nginx API Gateway (:80) ]
       ┌──────────────────────────────┬─────┴─────────────────────────┐
       ▼                              ▼                               ▼
[ public-gateway (Go) ]     [ realtime-gateway (Go) ]     [ REST Services (Python) ]
  • Виджет записи             • WebSockets (/ws)            • auth-service (:8001)
  • Свободные слоты           • SSE поток (/sse)            • catalog-service (:8002)
                                                            • inventory-service (:8009)
                                                            • pos-service (:8011)
  • Алгоритм «Любой мастер»   • Soft locks (edit:...)       • client-service (:8003)
                                                            • schedule-service (:8004)
                                                            • booking-service (:8005)
                                                            • finance-service (:8006)
                                                            • analytics-service (:8007)
                                                            • notification-service (:8008)
                                                            • admin-panel (:8000)
                                                                      │
                                                            [ scheduler-worker (Go) ]
                                                              • pg_advisory_lock
                                                              • автозавершение визитов
                                                                      │
       ┌──────────────────────────────────────────────────────────────┴────────────────┐
       ▼                                                                               ▼
[ PostgreSQL 16 ]                                                             [ Redis 7 / RabbitMQ 3 ]
  11 изолированных схем (auth, catalog, clients, inventory, pos,                Кэш слотов, Pub/Sub,
  schedule, booking, finance, analytics, notify, admin)                         Очереди событий
```

---

## 🚀 Быстрый старт

### 1. Требования
- Docker 24+ и Docker Compose v2/v5
- Make (опционально)
- Python 3.11+ и Go 1.22+ (для локальной разработки)

### 2. Запуск в Docker (Одной командой)

```bash
# Клонируйте репозиторий
git clone https://github.com/Fondante-GGG/NurCRM-Microservices.git
cd NurCRM-Microservices

# Запустите весь стек из backend/deploy
cd backend/deploy
docker compose up -d
```

Все 19 контейнеров запустятся автоматически. Доступные порты:
- **API Gateway:** `http://localhost:80`
- **Django Admin:** `http://localhost:80/admin/`
- **JWKS Endpoint:** `http://localhost:80/.well-known/jwks.json`
- **RabbitMQ Dashboard:** `http://localhost:15672` (гость: `guest` / `guest`)
- **PostgreSQL:** `localhost:5432` (`postgres` / `postgres_master_password`)

### 3. Остановка
```bash
docker compose down
```

---

## 🧪 Тестирование

```bash
# Запуск всех тестов (Python + Go)
make test

# Python тесты доменных правил, бронирования и POS/Inventory
make test-py

# Только Go тесты алгоритма свободных слотов и объединения
make test-go
```

---

## 📋 Каталог микросервисов

| Сервис | Стек | Схема БД | Назначение |
| :--- | :---: | :---: | :--- |
| **auth-service** | DRF | `auth` | Регистрация компаний, сотрудников, выдача JWT RS256, JWKS |
| **catalog-service** | DRF | `catalog` | Услуги, товары, категории, процентные ставки мастеров |
| **inventory-service** | DRF | `inventory` | Остатки товаров, движения и резервирование для продаж |
| **pos-service** | DRF | `pos` | Продажи с проверкой каталога и резервированием остатков |
| **client-service** | DRF | `clients` | База клиентов, история визитов, защищённые файлы документов |
| **schedule-service** | DRF | `schedule` | Расписание, GiST exclusion constraint `no_overlap`, автозавершение |
| **booking-service** | DRF | `booking` | Заявки на бронь, распределённая Сага подтверждения |
| **finance-service** | DRF | `finance` | Сдельные начисления ($price \times rate / 100$), выплаты зарплат, кассовые смены |
| **analytics-service** | FastAPI | `analytics` | Дашборды выручки, среднего чека, конверсии и рейтинги мастеров |
| **notification-service** | FastAPI | `notify` | WhatsApp/SMS напоминания клиентам за 24ч и за 2ч до визита |
| **admin-panel** | Django Admin | `admin` | Мульти-базовый роутер, аудит-лог изменений, read-only режим |
| **public-gateway** | Go | — | Быстрый движок доступности слотов онлайн-виджета («Любой мастер») |
| **realtime-gateway** | Go | — | WebSocket & SSE сервер с RBAC-фильтрацией и мягкими блокировками |
| **scheduler-worker** | Go | — | Периодический воркер (каждые 60с) с `pg_advisory_lock` |

---

## 🔒 Безопасность и конфигурация

Все секреты изолированы через переменные окружения:
- Файлы `.env` исключены из Git во всех сервисах.
- Шаблоны `.env.example` предоставлены для каждого сервиса.
- Межсервисные запросы защищены внутренними подписями `InternalServiceClient`.
- Доступ к документам клиентов (`/protected-media/`) защищён через Nginx `X-Accel-Redirect`.

---

## 📂 Структура репозитория

```
├── backend/
│   ├── deploy/                 # Docker Compose, Nginx gateway, SQL инициализация
│   ├── docs/                   # Детальная архитектурная и API документация
│   ├── libs/
│   │   ├── common/             # Python Value Objects, JWT, HTTP client, Outbox/Inbox
│   │   └── go_common/          # Go JWKS validator, Redis client, event models
│   ├── services/               # 12 микросервисов
│   ├── tests/                  # Автоматические тесты домена и use-case
│   └── Makefile                # Команды сборки и запуска
├── memory-bank/                # Системная память архитектурных решений
├── .github/workflows/          # GitHub Actions CI пайплайн
├── docker-compose.yml          # Корневой запуск
└── README.md
```

---

## 🔗 Связь с основным бэкендом NurCRM (Django)

Маркет, касса и склад пока работают в основном бэкенде [isko18/NurCRM](https://github.com/isko18/NurCRM). Правки к нему за 20–29.10.2026 открыты как PR:

- [#2](https://github.com/isko18/NurCRM/pull/2) — цены кассы
- [#3](https://github.com/isko18/NurCRM/pull/3) — все серверные правки 20–28.10 (ТЗ-28, ТЗ 11–12, Н-01…Н-33, Б-01…Б-87)
- [#4](https://github.com/isko18/NurCRM/pull/4) — аренда помещений
- [#5](https://github.com/isko18/NurCRM/pull/5) — PLU и штрихкоды архива, номер чека, фискальный чек eKassa
- [#6](https://github.com/isko18/NurCRM/pull/6) — фото глобального каталога

Ветки по отдельности: [YTArmen/NurCRM](https://github.com/YTArmen/NurCRM/branches). Подробная сводка: [`backend/docs/MONOLITH_CHANGES_2026-10.txt`](backend/docs/MONOLITH_CHANGES_2026-10.txt).
