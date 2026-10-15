# Руководство по развертыванию и запуску (Deployment Guide)

## 1. Системные требования

- **Docker:** версия 24.0+ и **Docker Compose** v2+
- **ОС:** Linux (Ubuntu 22.04+ / Debian 12+) или macOS
- **Порты по умолчанию:**
  - `80`: Единый Nginx Gateway (входная точка для SPA, виджета и мобильных клиентов)
  - `5432`: PostgreSQL 16 (схемы: `auth`, `catalog`, `clients`, `schedule`, `booking`, `finance`, `analytics`, `notify`, `admin`)
  - `6379`: Redis 7
  - `5672` / `15672`: RabbitMQ 3
  - `8000`: Django Admin Panel (внутренний порт)
  - `8010`: Public Gateway (Go)
  - `8020`: Realtime Gateway WebSocket/SSE (Go)

---

## 2. Быстрый запуск в Docker Compose

Все микросервисы, базы данных, брокеры сообщений и шлюз разворачиваются одной командой:

```bash
cd backend/deploy
docker compose up -d --build
```

### Проверка статуса контейнеров:
```bash
docker compose ps
```

### Просмотр логов любого сервиса:
```bash
docker compose logs -f gateway
docker compose logs -f schedule-service
docker compose logs -f public-gateway
```

---

## 3. Локальный запуск без Docker (Режим разработки)

### 3.1. Инициализация базы данных PostgreSQL
Выполните SQL-скрипт инициализации схем, ролей и расширений:
```bash
psql -h localhost -U postgres -d nurcrm -f backend/deploy/init-db/01_init.sql
```

### 3.2. Виртуальное окружение Python
```bash
python3 -m venv backend/.venv
source backend/.venv/bin/activate
pip install -r backend/requirements.txt
```

### 3.3. Запуск DRF-сервисов (пример для auth-service):
```bash
export PYTHONPATH="backend:."
python backend/services/auth/manage.py runserver 8001
```

### 3.4. Запуск FastAPI-сервисов (analytics-service):
```bash
export PYTHONPATH="backend:."
uvicorn backend.services.analytics.interface.main:app --port 8007 --reload
```

### 3.5. Запуск Go-сервисов (public-gateway, realtime-gateway, scheduler-worker):
```bash
cd backend/services/public-gateway && go run ./cmd/main.go
cd backend/services/realtime-gateway && go run ./cmd/main.go
cd backend/services/scheduler-worker && go run ./cmd/main.go
```

---

## 4. Запуск автоматических тестов

### Тесты Python (Clean Architecture, домен, инварианты, саги):
```bash
PYTHONPATH="backend:." backend/.venv/bin/pytest -v backend/tests/test_domain_and_use_cases.py
```

### Тесты Go (Availability Engine, Union calculation):
```bash
cd backend/services/public-gateway && go test -v ./...
```

---

## 5. Хранилище клиентских файлов

Файлы клиентов сохраняются на сервере в томе:
```
/var/lib/crm/media/clients/<company_id>/<client_id>/<uuid>
```
Выдача файлов наружу происходит строго через авторизованный запрос в `client-service` с использованием механизма **Nginx `X-Accel-Redirect`**, что исключает несанкционированный публичный доступ к медицинским картам, договорам и персональным фото посетителей.
