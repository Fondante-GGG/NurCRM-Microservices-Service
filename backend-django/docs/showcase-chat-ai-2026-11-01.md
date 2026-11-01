# Чат на витрине и ИИ-помощник (01.11.2026)

Для фронта витрины и разработчика кассы. Простыми словами.

## Адреса

Публичные адреса (без входа) доступны по двум префиксам, это одно и то же:
- `/api/main/public/companies/{slug}/chat/…` (рядом с остальной витриной);
- `/api/inbox/public/companies/{slug}/chat/…`.

Токен посетителя передаётся заголовком `X-Visitor-Token: <visitor_token>`.

| Что | Метод и адрес |
|---|---|
| Настройки чата | `GET chat/config/` |
| Начать сеанс | `POST chat/sessions/` |
| Написать / читать сообщения | `POST` и `GET chat/sessions/{id}/messages/?after=&wait=25` |
| Спросить помощника | `POST chat/sessions/{id}/assistant/` |
| «Продолжить в Telegram» | `GET chat/sessions/{id}/telegram-link/` |
| Передать телефон (с согласием) | `POST chat/sessions/{id}/consent/` |
| Удалить мой чат | `DELETE chat/sessions/{id}/` |

Для владельца (с входом, право `can_manage_channels`), префикс `/api/main/inbox/`:
- `GET/PUT assistant/settings/` — настройки помощника;
- `POST assistant/test/` — «Проверить помощника».

### Начать сеанс
```
POST chat/sessions/
{ "page": "/product/123", "turnstile_token": "<токен виджета Turnstile>" }
→ 201 { "session_id": "uuid", "visitor_token": "…", "expires_at": "…", "config": {…} }
```
Если на сервере задан секрет Turnstile, а токен не пришёл или неверный → `403 {"code":"turnstile_failed"}`.
Лимит 5 новых сеансов в минуту с одного IP (`429` и `Retry-After`).

### Сообщение посетителя
```
POST chat/sessions/{id}/messages/   { "text": "Здравствуйте", "client_msg_id": "m1" }
→ 201 { "message": {"id":1,"sender":"visitor","text":"…","kind":"text","created_at":"…"}, "duplicate": false }
```
Ответ сотрудника из «Чатов» приходит в `GET …/messages/` с `sender: "seller"`, ответ помощника с `sender: "assistant"`.

### Вопрос помощнику
```
POST chat/sessions/{id}/assistant/
{ "text": "Сколько стоит синее платье?", "lang": "ru", "client_msg_id": "q1" }
```
Ответ (всегда 200, смотрите `status`):
```
{
  "status": "ok",                      // ok | unavailable | busy | human | duplicate
  "answer": "Платье синее — в карточке ниже.",
  "cards": [ { "id": "uuid", "name": "Платье синее", "price": "1900.000", "unit": "шт",
               "in_stock": true, "image_url": "/media/…",
               "variants": [ {"id":"uuid","size":"M","color":"синий","price":"1900.00","in_stock":true} ] } ],
  "cart_actions": [ { "type": "add_to_cart", "product": "uuid", "variant": "uuid|null", "qty": 2,
                      "name": "…", "price": "1900.000", "line_total": "3800.00" } ],
  "handoff": null,                     // или { "requested": true, "reason": "…", "contacts": {…} }
  "cached": true                       // только если ответ из кэша (10 минут)
}
```
- Цены и остатки на экране фронт рисует из `cards`, а не из текста.
- Корзину ведёт фронт: если пришло `cart_actions`, добавьте строку в свою корзину.
- `status: "unavailable"` (помощник выключен, нет ключа, общий выключатель, ошибка модели):
  `{"status":"unavailable","unavailable":true,"answer":"Помощник сейчас недоступен…","handoff":{"requested":true,"contacts":{…}}}`.
- `status: "busy"` (лимит): `{"status":"busy","busy":true,"reason":"session_minute|session_day|ip_day|shop_day|message_rate","answer":"Помощник занят…","handoff":{…}}`.
- `contacts` для кнопок связи: `{ "phone": "+996…"|null, "telegram_url": "https://t.me/бот"|null, "whatsapp_url": "https://wa.me/996…"|null, "chat": true }`.
- `status: "human"`: в диалоге недавно ответил сотрудник, помощник молчит.
- Вопрос и ответ помощника пишутся в диалог, продавец видит их в «Чатах».

Функции модели: `search_products`, `get_product`, `get_size_chart`, `get_shop_info` (адрес, телефон, доставка, оплата, «Правила магазина»), `add_to_cart`, `handoff` (ставит диалогу «нужен человек»).

Защита от выдумок: все числа (от двух цифр) в тексте ответа должны быть в данных функций этого же хода или в вопросе. Иначе весь текст заменяется на «Уточню у продавца.», в журнале ходов `blocked = hallucination_blocked`. Карточки при этом остаются.

Лимиты: сеанс 6 в минуту и 40 в сутки, IP 120 в сутки, магазин `daily_cap` в сутки. Одинаковые вопросы (без учёта регистра и пробелов) в одном магазине и языке — из кэша 10 минут. Ответ с корзиной, передачей продавцу или блокировкой в кэш не попадает.

### Согласие на телефон
```
POST chat/sessions/{id}/consent/  { "consent": true, "phone": "+996700111222", "name": "Аня" }
→ 200 { "ok": true, "consent": true }
```
Без `consent: true` → `400 consent_required`. Согласие пишется в журнал (`ChatConsentLog`: сеанс, IP, время). Тот же журнал пишет и старый `POST …/contact/` при указании телефона. Сам помощник телефон не видит.

### Удалить мой чат
`DELETE chat/sessions/{id}/` с токеном → `200 {"ok":true,"deleted":N}`. Удаляются посетитель, диалог, сообщения и сеанс; тексты вопросов в журнале ходов стираются; журнал согласий остаётся (без ссылки на сеанс).

### «Продолжить в Telegram»
`GET chat/sessions/{id}/telegram-link/` → `{"url":"https://t.me/<бот>?start=w_<токен>"}` (токен до 40 символов, `[A-Za-z0-9_-]`). Когда посетитель нажмёт Start, серверный бот склеивает сеанс с его контактом Telegram (`WidgetSession.tg_contact`), старый телефон/клиент переносятся. `null`, если бот не подключён или в настройках чата выключено «Telegram».

## Настройки помощника (владелец)
```
GET /api/main/inbox/assistant/settings/
→ { "enabled": false, "daily_cap": 500, "knowledge": {"ru":"…"}, "knowledge_max_chars": 2000,
    "languages": ["ru","ky","en","uz","kk"], "key_set": true, "globally_disabled": false, "available": false }
PUT  /api/main/inbox/assistant/settings/   { "enabled": true, "daily_cap": 300, "knowledge": {"ru":"Обмен 14 дней…","kk":"…"} }
POST /api/main/inbox/assistant/test/       { "text": "Сколько стоит доставка?", "lang": "ru" }
→ { "ok": true, "answer": "…", "cards": [], "tools": ["get_shop_info"], "blocked": null }
   // или { "ok": false, "reason": "no_key|disabled|global_off|model_error" }
```
- Языки как в дизайне витрины: ru, ky, en, uz, kk (в ТЗ написано `kz`; взят `kk`, как в `design_schema.LANGUAGES`). До 2000 символов на язык.
- Ключ Gemini самого магазина (раздел бота), в ответах его нет никогда. Нет ключа → помощник «недоступен» и показывает кнопки связи.
- Проверка помощника лимиты не тратит и в диалоги не пишется.
- В capabilities (`/api/main/capabilities/`) добавлены `showcase_chat` и `showcase_assistant`.

## Переменные окружения
| Имя | Зачем |
|---|---|
| `TURNSTILE_SECRET_KEY` | секрет Cloudflare Turnstile; не задан — проверка пропускается (в логе предупреждение) |
| `SHOWCASE_ASSISTANT_DISABLED=1` | общий выключатель помощника на всём сервере (или `SHOWCASE_ASSISTANT_ENABLED=False` в settings) |

Ключ Gemini в env **не** используется (только ключ магазина).

## Очистка
`python manage.py purge_showcase_chats [--days 90]` — удаляет посетителей витрины старше срока (с диалогами и сообщениями; если посетитель писал позже границы — оставляет) и старый журнал ходов. Повторный запуск безопасен. Поставить в cron раз в сутки.

## Миграции
`inbox 0002_showcase_assistant`: поле `WidgetSession.tg_contact` и три новые таблицы (`AssistantSettings`, `AssistantTurn`, `ChatConsentLog`). Лёгкая, без блокировок существующих данных.

## Что не сделано
- Блок `shop.info.knowledge` в черновике дизайна витрины (`design/draft/`) не добавлен: правила хранятся в отдельных настройках помощника (эндпоинт выше). Если нужно слать из редактора сайта по «Сохранить», это одна правка в схеме дизайна, отдельно от параллельной работы в `apps/main`.
- Реальный вызов Gemini в тестах не проверялся (везде подмена); проверить вручную с настоящим ключом магазина.
- Токены считаются по длине текста (≈ символов/4): Gemini-обёртка их не возвращает.
- Лимиты считаются по журналу ходов в базе, не по Redis (точно, но дороже при очень большой нагрузке).
- Нет автоответа помощника в Telegram по ссылке `w_`; склейка сеанса есть, но сам помощник отвечает только на витрине.
- Ответы про наличие учитывают только скрытие товара в витрине, отдельной проверки «опубликован ли товар» нет.
- Cloudflare Turnstile на фронте (виджет) не входит в бэкенд.
