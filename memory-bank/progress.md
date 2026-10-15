# Progress: Прогресс реализации и статус приёмки

## 1. Статус этапов реализации (по разделу 13 ТЗ)

| Этап | Состав этапа | Критерий приёмки | Статус |
| :---: | :--- | :--- | :---: |
| **1** | Инфраструктура, auth, catalog, client, admin-panel | Вход по JWT (RS256/JWKS), CRUD услуг и клиентов, раздельные схемы БД, админка читает все схемы через мульти-роутер | **Выполнено (100%)** |
| **2** | schedule + outbox/inbox + RabbitMQ | Запись без накладок (PostgreSQL GiST exclusion constraint `no_overlap`), контроль длительностей и снапшотов услуг | **Выполнено (100%)** |
| **3** | public-gateway (Go) + booking | Виджет рассчитывает свободные слоты мастера и «Любой мастер», подтверждение заявки (Сага) создает клиента и запись | **Выполнено (100%)** |
| **4** | scheduler-worker + finance | Визит завершается автоматически каждые 60с (с `pg_advisory_lock`), начисление создается ровно 1 раз (уникальный `appointment_id`) | **Выполнено (100%)** |
| **5** | analytics (FastAPI) | Дашборд руководителю: выручка, конверсия, средний чек, графики пиковых дней и денежных потоков | **Выполнено (100%)** |
| **6** | notification | Создание нотификаций и планирование напоминаний клиентам за 24 часа и за 2 часа до визита | **Выполнено (100%)** |
| **7** | realtime-gateway (Go) + оптимистичные блокировки | WebSocket/SSE сервер, доставка изменений в комнату компании, мягкие блокировки `edit:{entity}:{id}`, заголовок `If-Match: version` | **Выполнено (100%)** |

---

## 2. Что создано и работает (Checklist)

- [x] **PostgreSQL Схема и Роли (`backend/deploy/init-db/01_init.sql`):** 9 логических схем, 9 выделенных пользователей, отсутствие межсхемных FK/JOIN.
- [x] **Общая библиотека Python (`backend/libs/common`):** `Money`, `Phone`, `TimeSlot`, `EventEnvelope`, `OutboxRecord`, `InboxRecord`, `InternalServiceClient`, генератор и валидатор JWT RS256/JWKS.
- [x] **Общая библиотека Go (`backend/libs/go_common`):** `events`, `jwks`, `redis`.
- [x] **auth-service:** DRF + PyJWT, аутентификация, профили, компании, JWKS `/.well-known/jwks.json`.
- [x] **catalog-service:** DRF, категории, услуги, процентные ставки мастеров.
- [x] **client-service:** DRF, клиентская база, защищенное хранилище документов на диске (`/var/lib/crm/media/clients/...`), история визитов.
- [x] **schedule-service:** DRF, расписание, контроль пересечений, автозавершение визитов.
- [x] **booking-service:** DRF, прием заявок, Сага сквозного подтверждения с вызовом client и schedule.
- [x] **finance-service:** DRF, начисления сдельной оплаты ($price \times rate / 100$), выплаты зарплат, кассовые смены (с защитой от параллельного открытия), склад расходников.
- [x] **analytics-service:** FastAPI, расчет метрик, конверсии и рейтингов.
- [x] **notification-service:** FastAPI + worker, WhatsApp/SMS, напоминания.
- [x] **admin-panel:** Django Admin с мульти-базовым роутером и аудит-логом.
- [x] **public-gateway:** Go, Availability Engine для виджета онлайн-записи, кэш Redis.
- [x] **scheduler-worker:** Go, периодический воркер (60с) с `pg_advisory_lock`.
- [x] **realtime-gateway:** Go, WebSocket и SSE сервер с RBAC-фильтрацией и мягкими блокировками.
- [x] **Развертывание (`backend/deploy`):** `docker-compose.yml`, `nginx.conf`, `Dockerfile.*`.
- [x] **Запуск одной командой (`docker compose up -d`):** Корневой и бэкенд `docker-compose.yml` настроены через `include:`. Все 16 контейнеров (Postgres 16, Redis 7, RabbitMQ 3, Nginx Gateway, 9 Python-сервисов, 3 Go-сервиса) поднимаются и работают стабильно без ошибок.
- [x] **Конфигурация окружения и безопасности:** Созданы `.gitignore`, `.env.example` и рабочие локальные `.env` для всех 12 микросервисов, корня бэкенда и проекта. Все секреты надёжно исключены из репозитория.
- [x] **Утилиты сборки и запуска (`backend/Makefile`):** Удобные команды `make test`, `make build-go`, `make docker-up`, `make docker-down`.
- [x] **Документация (`backend/docs`):** `ARCHITECTURE.md`, `API_REFERENCE.md`, `DEPLOYMENT.md`.
- [x] **Автоматические тесты (`backend/tests`):** Python (pytest, 11 тестов) и Go (2 теста) — 100% PASS.

---

## 3. Следующие шаги
- Подключение клиентского веб-приложения (React SPA) и публичного виджета онлайн-записи к API Gateway (`http://localhost`).
- Настройка production SSL-сертификатов при развертывании на внешнем домене.
