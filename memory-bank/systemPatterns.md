# System Patterns: Архитектурные паттерны и решения

## 1. Чистая архитектура (Clean Architecture) и DDD

Каждый сервис разделен на 4 независимых слоя со строгим правилом направления зависимостей (только внутрь):

```
       [ Interface Layer ]       (DRF Views, FastAPI Routers, Go Handlers)
                ↓
      [ Application Layer ]      (Use Cases, DTOs, Unit of Work Ports, Clients)
                ↓
        [ Domain Layer ]         (Aggregates, Entities, Value Objects, Domain Events)
                ↑
    [ Infrastructure Layer ]     (Django ORM / SQL, Outbox, Redis, FileStorage)
```

- **Domain:** не зависит от Django, фреймворков и БД. Все инварианты проверяются внутри сущностей.
- **Application:** координирует бизнес-сценарии через транзакционный Unit of Work. Не вызывает `save()` напрямую.
- **Infrastructure:** реализует порты хранения, внешних вызовов и брокеров.
- **Interface:** валидирует входящий запрос и формирует стандартизированный ответ.

---

## 2. Изоляция СУБД (Single Database with Schema Isolation)

Система работает поверх единого инстанса PostgreSQL 16 с гарантией готовности к моментальному выносу любого сервиса в отдельную БД простой сменой DSN.

### Правила изоляции:
1. **Одна схема на сервис:** `auth`, `catalog`, `clients`, `schedule`, `booking`, `finance`, `analytics`, `notify`, `admin`.
2. **Никаких FK и JOIN между схемами:** кросс-сервисные ссылки хранятся строго в виде UUID (`client_id`, `barber_id`, `service_id`).
3. **Отдельная роль БД для каждого сервиса:** `svc_auth`, `svc_schedule` и т.д., имеющая доступ только к своей схеме.
4. **Отказоустойчивые ограничения на уровне PostgreSQL:**
   - Защита от пересечений записей мастера:
     ```sql
     ALTER TABLE schedule.appointments ADD CONSTRAINT no_overlap
     EXCLUDE USING gist (barber_id WITH =, tstzrange(start_at, end_at) WITH &&)
     WHERE (status IN ('booked','confirmed','completed'));
     ```
   - Защита от дублей зарплаты: поле `appointment_id` в `finance.accruals` объявлено `UNIQUE`.
   - Защита от дублей кассовых смен:
     ```sql
     CREATE UNIQUE INDEX idx_open_shift_per_box ON finance.cash_shifts (company_id, cashbox)
     WHERE (status = 'open');
     ```

---

## 3. Асинхронное взаимодействие: Transactional Outbox и Inbox

Для исключения потери событий при сбоях сети используется паттерн **Transactional Outbox**:
- Бизнес-сущность и запись о событии в таблице `outbox` сохраняются в одной транзакции PostgreSQL.
- Потребители событий используют таблицу `inbox` с первичным ключом `event_id`, что гарантирует идемпотентность повторной доставки.

### Каталог событий (Topic Exchange `crm.events`):
- `auth.company.changed`, `auth.employee.changed`
- `catalog.service.changed`
- `client.client.created`, `client.client.updated`
- `schedule.appointment.created`, `schedule.appointment.updated`, `schedule.appointment.canceled`, `schedule.appointment.completed`
- `booking.request.created`, `booking.request.confirmed`
- `finance.payout.created`, `finance.shift.closed`

---

## 4. Конкурентность и многопользовательская работа

1. **Оптимистичная блокировка:** поле `version` увеличивается на 1 при каждом изменении агрегата. Клиенты передают заголовок `If-Match: <version>`. Сервер выполняет `UPDATE ... WHERE id = ? AND version = ?`. При несовпадении возвращается `409 version_conflict`.
2. **Мягкие блокировки (Soft Locks):** при начале редактирования карточки клиентом через WebSocket в Redis создается ключ `edit:{entity}:{id}` с TTL 60 сек («Сотрудник сейчас редактирует эту запись»).
3. **Idempotency-Key:** все мутирующие операции (создание записей, проведение выплат) принимают заголовок `Idempotency-Key` для защиты от повторной отправки форм.

---

## 5. Отказоустойчивый AI-Ассистент (Cascading Multi-Provider Fallback)

Для обеспечения непрерывной доступности консультанта по услугам в `front-usluga` реализован каскадный паттерн обработки запросов:

```
[ Пользователь / Вопрос по услугам ]
                 ↓
     [ Next.js API /api/ai/chat ]
                 ↓
     [ Попытка 1: Google Gemini ] ──(Успех)──> Ответ клиенту
                 ↓ (Ошибка / Таймаут)
     [ Попытка 2: Anthropic Claude ] ──(Успех)──> Ответ клиенту
                 ↓ (Ошибка / Таймаут)
     [ Попытка 3: OpenAI Codex/GPT ] ──(Успех)──> Ответ клиенту
                 ↓ (Все 3 недоступны)
     [ Graceful Maintenance Banner: «Техническое обслуживание» ]
```

- **Инъекция контекста:** Системный промпт динамически наполняется срезом активных услуг, цен, мастеров и филиалов текущей компании.
- **Изоляция секретов:** Обращения к AI-провайдерам выполняются строго на стороне сервера (Server-side API Route), предотвращая утечку API-токенов в браузер.
- **Сохранение сессии:** Виджет внедрен в корневой макет `RootLayout`, благодаря чему история чата и состояние открытости не сбрасываются при переходе между страницами CRM.
