# Справочник REST API (API Reference) NurCRM Backend

Данный документ содержит полную спецификацию всех внешних эндпоинтов, их legacy-алиасов для обратной совместимости с существующим фронтендом, а также внутренних межсервисных эндпоинтов (`/internal/v1/`).

---

## 1. Общие стандарты

### Формат успешного ответа с пагинацией:
```json
{
  "count": 142,
  "results": [ ... ],
  "limit": 20,
  "offset": 0
}
```

### Формат ошибки (RFC 7807 адаптированный):
```json
{
  "code": "slot_busy",
  "message": "Selected time slot is already booked for this master.",
  "details": {},
  "trace_id": "8f8b89e2-3490-4a88-8255-a50cbe9f1c7d"
}
```

### Коды ошибок:
- `400 validation_error`: Некорректные входные данные
- `401 unauthorized`: Токен отсутствует, истек или недействителен
- `403 forbidden`: Недостаточно прав для выполнения действия
- `404 not_found`: Сущность не найдена
- `409 slot_busy`: Слот мастера уже занят другой записью
- `409 version_conflict`: Оптимистичная блокировка (версия в `If-Match` устарела)
- `409 already_processed`: Заявка уже была подтверждена другим администратором
- `409 shift_already_open`: Смена по данной кассе уже открыта
- `409 client_exists`: Клиент с таким телефоном уже зарегистрирован
- `429 rate_limit_exceeded`: Превышен лимит запросов

---

## 2. Спецификация эндпоинтов по сервисам

### 2.1. auth-service

| Метод | Путь v1 | Legacy Алиас | Доступ | Назначение |
| :--- | :--- | :--- | :--- | :--- |
| `GET` | `/.well-known/jwks.json` | — | Публичный | Публичные ключи RS256 для валидации JWT |
| `POST` | `/api/v1/auth/login/` | `/api/users/auth/login/` | Публичный | Вход по `email` + `password` |
| `POST` | `/api/v1/auth/refresh/`| `/api/users/auth/refresh/` | Публичный | Выпуск нового access-токена по refresh-токену |
| `GET` | `/api/v1/auth/profile/`| `/api/users/profile/` | Авторизован | Профиль текущего пользователя и его права |
| `GET` | `/api/v1/auth/company/`| `/api/users/company/` | Авторизован | Настройки компании (часы работы, тариф) |
| `GET` | `/api/v1/auth/employees/` | — | Владелец, Админ | Список сотрудников компании |
| `POST` | `/api/v1/auth/employees/` | — | Владелец, Админ | Добавление нового сотрудника |

#### Внутренний API auth-service:
- `GET /internal/v1/companies/{id}/` — параметры компании по UUID
- `GET /internal/v1/companies/slug/{slug}/` — параметры компании по slug (для онлайн-виджета)
- `GET /internal/v1/masters/` — список активных мастеров компании

---

### 2.2. catalog-service

| Метод | Путь v1 | Legacy Алиас | Доступ | Назначение |
| :--- | :--- | :--- | :--- | :--- |
| `GET, POST` | `/api/v1/catalog/categories/` | `/api/barbershop/service-categories/` | Авторизован | Категории услуг |
| `DELETE` | `/api/v1/catalog/categories/{id}/` | `/api/barbershop/service-categories/{id}/` | Владелец, Админ | Удаление категории |
| `GET, POST` | `/api/v1/catalog/services/` | `/api/barbershop/services/` | Авторизован | Список / создание услуг |
| `PATCH, DELETE`| `/api/v1/catalog/services/{id}/` | `/api/barbershop/services/{id}/` | Владелец, Админ | Изменение (`If-Match: version`) / удаление |
| `GET` | `/api/v1/catalog/rates/` | `/api/barbershop/salary/rates/` | `can_view_salary` | Ставки мастеров по услугам |
| `PUT` | `/api/v1/catalog/rates/{service_id}/` | `/api/barbershop/salary/rates/{service_id}/` | `can_view_salary` | Установка ставки мастера |

#### Внутренний API catalog-service:
- `GET /internal/v1/services/?company_id=...&service_ids=id1,id2` — получение цен и длительностей услуг для фиксации snapshot в записи
- `GET /internal/v1/rates/{service_id}/?company_id=...&master_id=...` — получение % ставки для начисления зарплаты
- `GET /internal/v1/products/?company_id=...&product_ids=id1,id2` — получение активных товаров и цен для POS

Товары доступны через `GET, POST /api/v1/catalog/products/` и `GET, PATCH /api/v1/catalog/products/{id}/`. Создание и изменение доступны владельцу, администратору и поддержке; себестоимость не возвращается обычным пользователям.

---

### 2.3. client-service

| Метод | Путь v1 | Legacy Алиас | Доступ | Назначение |
| :--- | :--- | :--- | :--- | :--- |
| `GET, POST` | `/api/v1/clients/` | `/api/barbershop/clients/` | `can_view_barber_clients` | Клиентская база / создание |
| `GET, PATCH, DELETE` | `/api/v1/clients/{id}/` | `/api/barbershop/clients/{id}/` | `can_view_barber_clients` | Просмотр, правка (`If-Match`), удаление |
| `GET, POST` | `/api/v1/clients/{id}/documents/` | `/api/barbershop/clients/{id}/documents/` | `can_view_barber_clients` | Список / загрузка файлов (`multipart/form-data`) |
| `DELETE` | `/api/v1/clients/{id}/documents/{doc_id}/` | `/api/barbershop/clients/{id}/documents/{doc_id}/` | `can_view_barber_clients` | Удаление документа |
| `GET` | `/api/v1/clients/{id}/documents/{doc_id}/download/` | — | `can_view_barber_clients` | Скачивание файла (защищено X-Accel-Redirect) |
| `GET` | `/api/v1/clients/{id}/visits/history/` | `/api/barbershop/clients/{id}/visits/history/` | `can_view_barber_history` | Полная история визитов |

#### Внутренний API client-service:
- `POST /internal/v1/clients/find-or-create/` — поиск по телефону или создание карточки клиента при подтверждении онлайн-заявки

---

### 2.4. schedule-service

| Метод | Путь v1 | Legacy Алиас | Доступ | Назначение |
| :--- | :--- | :--- | :--- | :--- |
| `GET, POST` | `/api/v1/schedule/appointments/` | `/api/barbershop/appointments/` | `can_view_barber_records` | Журнал записей / создание записи |
| `GET, PATCH, DELETE`| `/api/v1/schedule/appointments/{id}/`| `/api/barbershop/appointments/{id}/` | `can_view_barber_records` | Карточка записи / смена статуса / отмена |
| `GET` | `/api/v1/schedule/appointments/my/` | `/api/barbershop/appointments/my/` | Роль `master` | Личное расписание вошедшего мастера |

#### Внутренний API schedule-service:
- `GET /internal/v1/appointments/busy-slots/?company_id=...&master_id=...&date=...` — занятые интервалы для Availability Engine
- `POST /internal/v1/appointments/auto-complete/` — фоновый вызов от scheduler-worker раз в 60 сек
- `POST /internal/v1/appointments/` — создание записи при подтверждении Саги (с `Idempotency-Key`)

---

### 2.5. booking-service

| Метод | Путь v1 | Legacy Алиас | Доступ | Назначение |
| :--- | :--- | :--- | :--- | :--- |
| `GET, POST` | `/api/v1/bookings/` | `/api/barbershop/bookings/` | `can_view_barber_records` | Список входящих заявок с сайта |
| `GET, PATCH`| `/api/v1/bookings/{id}/` | `/api/barbershop/bookings/{id}/` | `can_view_barber_records` | Смена статуса / подтверждение заявки (Сага) |

#### Внутренний API booking-service:
- `POST /internal/v1/bookings/` — создание заявки, поступающей из публичного виджета

---

### 2.6. finance-service

| Метод | Путь v1 | Legacy Алиас | Доступ | Назначение |
| :--- | :--- | :--- | :--- | :--- |
| `GET, POST` | `/api/v1/finance/shifts/` | `/api/construction/shifts/` | `can_view_cashbox` | Кассовые смены / открытие смены |
| `POST` | `/api/v1/finance/shifts/{id}/close/` | `/api/construction/shifts/{id}/close/` | `can_view_cashbox` | Закрытие кассовой смены |
| `GET` | `/api/v1/finance/salary/accruals/` | `/api/barbershop/salary/accruals/` | `can_view_salary` | Журнал начислений сдельной оплаты |
| `GET, POST` | `/api/v1/finance/salary/payouts/` | `/api/barbershop/salary/payouts/` | `can_view_salary` | Журнал / проведение выплаты зарплаты |
| `GET` | `/api/v1/finance/salary/summary/` | `/api/barbershop/salary/summary/` | `can_view_salary` | Сводка: Начислено, Выплачено, Баланс |
| `GET, POST` | `/api/v1/finance/warehouse/materials/` | — | Владелец, Админ | Склад материалов и расходников |

#### Внутренний API finance-service:
- `POST /internal/v1/finance/accruals/process-completed/` — триггер создания начисления по завершенному визиту (защищен от дублей)

---

### 2.7. analytics-service (FastAPI)

| Метод | Путь v1 | Legacy Алиас | Доступ | Назначение |
| :--- | :--- | :--- | :--- | :--- |
| `GET` | `/api/v1/analytics/dashboard/` | `/api/barbershop/analytics/dashboard/` | `can_view_cashbox` | Сводный дашборд, конверсия визитов, рейтинги мастеров и услуг |

---

### 2.8. public-gateway (Go)

| Метод | Путь | Доступ | Назначение |
| :--- | :--- | :--- | :--- |
| `GET` | `/api/barbershop/public/{slug}/service-categories/` | Публичный | Категории услуг для виджета онлайн-записи |
| `GET` | `/api/barbershop/public/{slug}/services/` | Публичный | Каталог услуг для виджета (кэш в Redis) |
| `GET` | `/api/barbershop/public/{slug}/masters/` | Публичный | Список мастеров с фото и должностями |
| `GET` | `/api/barbershop/public/{slug}/masters/availability/` | Публичный | Расчет доступных слотов на дату (шаг 15/30 мин) |
| `POST`| `/api/barbershop/public/{slug}/bookings/` | Публичный | Оформление клиентской онлайн-заявки |

---

### 2.9. realtime-gateway (Go)

| Протокол | Путь | Доступ | Назначение |
| :--- | :--- | :--- | :--- |
| `WebSocket` | `/ws` (или `?token=...`) | Авторизован | Двунаправленный канал мгновенных событий и блокировок |
| `SSE` | `/sse` | Авторизован | Резервный поток серверных событий |

---

### 2.10. inventory-service

| Метод | Путь v1 | Legacy Алиас | Доступ | Назначение |
| :--- | :--- | :--- | :--- | :--- |
| `GET` | `/api/v1/inventory/stock/` | `/api/main/warehouse/stock/` | Авторизован | Остатки по товару и филиалу |
| `POST` | `/api/v1/inventory/movements/` | `/api/main/warehouse/movements/` | Владелец, Админ, Поддержка | Приход, возврат или списание товара |

#### Внутренний API inventory-service:
- `POST /internal/v1/reservations/` — идемпотентно резервирует количество в остатках.
- `POST /internal/v1/reservations/{id}/commit/` — подтверждает резерв и списывает товар.
- `POST /internal/v1/reservations/{id}/release/` — освобождает незавершенный резерв.

### 2.11. pos-service

| Метод | Путь v1 | Legacy Алиас | Доступ | Назначение |
| :--- | :--- | :--- | :--- | :--- |
| `GET` | `/api/v1/pos/sales/` | `/api/main/pos/sales/` | Кассир, Владелец, Админ или `can_view_cashbox` | Список продаж |
| `POST` | `/api/v1/pos/sales/` | `/api/main/pos/checkout/`, `/api/main/pos/sales/` | Кассир, Владелец, Админ или `can_view_cashbox` | Оформление продажи |
| `GET` | `/api/v1/pos/sales/{id}/` | `/api/main/pos/sales/{id}/` | Кассир, Владелец, Админ или `can_view_cashbox` | Детали продажи |

Checkout принимает `items` с `product_id`, `quantity`, `unit_code` и необязательными `variant_id`, `branch_id`, `location_code`, `discount`; все строки одной продажи должны относиться к одному филиалу. Заголовок `Idempotency-Key` обязателен. Статусы продажи: `pending_inventory`, `completed`, `rejected`. POS вызывает Catalog и Inventory через внутренние подписанные API; внутренние маршруты не публикуются через Nginx.
