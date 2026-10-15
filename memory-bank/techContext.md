# Tech Context: Технологический стек и окружение

## 1. Стек технологий

| Компонент | Технология | Обоснование |
| :--- | :--- | :--- |
| **Бизнес-сервисы** | Python 3.11+, Django 5.x, DRF | Высокая скорость разработки CRUD, развитая валидация, транзакционность |
| **Аналитика и нотификации** | FastAPI, Pydantic v2, Uvicorn | Высокая скорость сериализации, асинхронный ввод/вывод для фоновых задач |
| **Высоконагруженные шлюзы** | Go 1.22+ | Минимальное потребление памяти, быстрый параллельный расчет слотов (p95 < 50мс), 1000+ одновременных WebSocket-соединений |
| **База данных** | PostgreSQL 16 | Логические схемы, поддержка расширения `btree_gist` для exclusion constraints |
| **Кэш и быстрые блокировки** | Redis 7 | Кэширование публичного каталога (`pub:{slug}:services`), занятых слотов и мягких блокировок |
| **Брокер сообщений** | RabbitMQ 3 (Topic Exchange) | Гарантированная доставка событий, durable-очереди, DLQ |
| **Безопасность / Auth** | PyJWT (RS256), JWKS, PBKDF2 | Локальная проверка подписи токенов сервисами без сетевых походов в auth |
| **Reverse Proxy / Gateway** | Nginx | Единая точка входа (порт 80), маршрутизация, раздача файлов через `X-Accel-Redirect` |

---

## 2. Карта портов и сервисов

| Сервис | Контейнер / Порт | Назначение |
| :--- | :--- | :--- |
| **gateway** | `:80` | Единый Nginx Reverse Proxy |
| **admin-panel** | `:8000` | Django Admin панель |
| **auth-service** | `:8001` | Аутентификация, JWT, профили и компании |
| **catalog-service** | `:8002` | Услуги, категории, ставки |
| **client-service** | `:8003` | Клиенты, файлы документов |
| **schedule-service** | `:8004` | Расписание, журнал записей |
| **booking-service** | `:8005` | Онлайн-заявки, сага подтверждения |
| **finance-service** | `:8006` | Сдельная зарплата, смены, склад |
| **analytics-service** | `:8007` | Дашборды, рейтинги, конверсия |
| **notification-service** | `:8008` | WhatsApp/SMS напоминания |
| **public-gateway** | `:8010` | Публичный виджет записи (Go) |
| **realtime-gateway** | `:8020` | WebSocket/SSE сервер (Go) |
| **scheduler-worker** | фоновый процесс | Фоновое автозавершение визитов раз в 60 сек |
| **postgres** | `:5432` | СУБД PostgreSQL 16 |
| **redis** | `:6379` | Кэш и Pub/Sub |
| **rabbitmq** | `:5672` / `:15672` | Брокер сообщений |

---

## 3. Пользователи и роли СУБД

Все пароли сервисов вынесены в переменные окружения (по умолчанию для локального dev: `svc_<name>_secret`):
- `svc_auth` $\to$ `search_path = auth, public`
- `svc_catalog` $\to$ `search_path = catalog, public`
- `svc_clients` $\to$ `search_path = clients, public`
- `svc_schedule` $\to$ `search_path = schedule, public`
- `svc_booking` $\to$ `search_path = booking, public`
- `svc_finance` $\to$ `search_path = finance, public`
- `svc_analytics` $\to$ `search_path = analytics, public`
- `svc_notify` $\to$ `search_path = notify, public`
- `svc_admin` $\to$ чтение всех схем, запись в `admin`
