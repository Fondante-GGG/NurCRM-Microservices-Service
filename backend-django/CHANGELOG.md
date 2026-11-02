# CHANGELOG бэкенда (ветка feature/tz26-b52-b87)

Новые записи сверху. Единое ТЗ бэкенду 26.10.2026, разделы 8–11 (Б-52…Б-87).

## 03.11.2026 — серверные фильтры чеков и приходов
- `GET main/pos/sales/?payment_method=noncash` — «Безнал»: всё, кроме `cash` и `debt` (transfer, mbank, optima, obank, bakai, mixed, offset). Можно списком: `payment_method=cash,debt` (transfer в списке — вместе с банками). Одно значение — как раньше.
- `GET main/suppliers/receipts/`: `created_by=<uuid>` («кто»), `amount_min` / `amount_max` (сумма прихода), `product_search` (товар: название/штрихкод/код; строки прихода не урезаются). `count` и `meta.total_amount` — с учётом фильтров.
- `capabilities.features`: `cashflow_employee`, `product_thumbs`, `sales_noncash_filter`, `receipts_filters`.

## 03.11.2026 — миниатюры фото товаров
- `ProductImage.thumb`: при загрузке фото делается миниатюра WebP 320px по большей стороне (`products/<id>/thumbs/`); удаляется вместе с фото. Не получилось — фото всё равно сохраняется.
- В API: `image_thumb_url` у каждой картинки (`images[]` в `main/products/list/`, карточка, POS) и у `ProductListSerializer`. `null` — миниатюры ещё нет, брать `image_url`.
- Миграция main 0172 (колонка NULL, мгновенно). `manage.py make_product_thumbs [--dry-run] [--limit N] [--batch 200] [--company]` — для старых фото, можно прерывать.

## 03.11.2026 — выплаты зарплаты: id сотрудника в расходе
- `CashFlow.employee` (необязательная ссылка на сотрудника своей компании): `POST/PATCH construction/cashflows/` принимает `employee`, в ответе `employee` и `employee_name`. Выплаты `main/market-salary/payouts/` (и их отмена) ставят его сами.
- `?employee=<id>`: строки с `employee` — по нему, старые строки без него — по кассиру (как в ТЗ Н-19); `?employee_strict=1` — только по `employee`.
- Миграция construction 0039 (Postgres: колонка, FK NOT VALID, индекс CONCURRENTLY; atomic=False).
- `manage.py backfill_cashflow_employee [--apply] [--company] [--batch 500]`: по id выплаты MarketSalaryPayout и по названию «Зарплата: Имя» (тёзки пропускаются). Без `--apply` только отчёт.
## 01.11.2026 — редактор накладных: скидка, цена продажи, history
- `PATCH suppliers/receipts/{id}/`: шапка `discount` (сумма / `"10%"`) и `discount_percent`; пересчитывает закупку (и `landed_price`) строк пропорционально, как при проведении; идёт в итог, долг поставщику, кассу, `deltas.header`, снимок версии; откат версии возвращает скидку. 422 `discount_exceeds_total`.
- Строка `lines[].sale_price` (+ `update_product_sale_price`, по умолчанию true): меняет цену продажи строки и товара (наценка от закупки), `deltas.sale_price[]`, предупреждение `sale_price_not_latest`; откат цену товара не трогает.
- `GET suppliers/receipts/{id}/history/` — псевдоним `versions/`. Признаки `receipt_edit_discount`, `receipt_edit_sale_price`. НДС не поддерживается (поля нет). Миграций нет.
## 01.11.2026 — Витрина P0 (ветка feature/showcase-p0)
- Публичный дизайн: блок `telegram` `{enabled, url, product_url_template, placement, label}` (бот server + webhook + `cart.telegram.enabled`; токена нет). Ключи дизайна `cart.telegram.*`.
- Заказ витрины: `source_detail`, `source=web_chat`, `cart_token` (один токен — один заказ, повтор → 200), фильтр `?source_detail=`; поля в списке и карточке.
- `POST public/companies/{slug}/cart-link/` → `{token}` (7 дней, 20/час с IP); бот: `/start c_<token>` (корзина по ценам из базы, оформление) и `/start p_<id>` (карточка товара).
- События `assistant_open`, `assistant_message`, `telegram_click`, `cart_link` + счётчики в статистике.
- Ключ дизайна `shop.info.knowledge` (закрытый, ru/ky/en/uz/kk, до 2000) и `get_shop_knowledge(company, lang)`.
- Касса: `SaleItem.line_total` и `cart_service._money` — ROUND_HALF_UP; `branch-transfers/` принимает `idempotency_key` в теле; `debt_adjustment.remaining_debt` при возврате долговой продажи = до − погашено.
- capabilities: `showcase_telegram`, `showcase_cart_link`, `showcase_order_source_detail`.
- Миграция: main 0171_showcase_p0_1101. Описание: docs/showcase-p0-2026-11-01.md.
## 01.11.2026 — ТЗ Умару: чат на витрине и ИИ-помощник (пункты 5–9)
- ИИ-помощник витрины (`apps/inbox/assistant.py`): `POST …/chat/sessions/{id}/assistant/`. Ключ Gemini — только ключ самого магазина (настройки его бота), общего ключа NurCRM нет, в ответах ключа нет. Функции `search_products`, `get_product`, `get_size_chart`, `get_shop_info`, `add_to_cart`, `handoff`; ответ с карточками товаров и строкой корзины для фронта. Сверка чисел с данными функций того же хода: расхождение → «Уточню у продавца.» и `hallucination_blocked` в журнале ходов.
- Защита: Turnstile при создании сеанса (env `TURNSTILE_SECRET_KEY`, нет — пропуск с предупреждением), лимиты 6/мин и 40/сутки на сеанс, 120/сутки на IP, потолок магазина `daily_cap`, кэш одинаковых вопросов 10 мин, выключатели (магазин и глобально `SHOWCASE_ASSISTANT_DISABLED=1`), журнал ходов `AssistantTurn`.
- «Правила магазина» (`knowledge`, до 2000 символов, ru/ky/en/uz/kk) и настройки помощника владельца: `GET/PUT api/main/inbox/assistant/settings/`, «Проверить помощника» `POST api/main/inbox/assistant/test/`.
- Согласие на телефон `POST …/consent/` (журнал `ChatConsentLog`), «Удалить мой чат» `DELETE …/sessions/{id}/`, `manage.py purge_showcase_chats` (90 дней, повторный запуск безопасен).
- Чат под `api/main/public/companies/{slug}/chat/…` (то же, что `api/inbox/public/…`); `/start w_<токен>` склеивает сеанс с контактом Telegram (`WidgetSession.tg_contact`), бот не принимает метку за телефон.
- capabilities: `showcase_chat`, `showcase_assistant`. Миграция: inbox 0002_showcase_assistant (лёгкая, новые таблицы).

## 31.10.2026 — ТЗ «Редактор накладных закупок» (30.10), вариант А
- `PATCH api/main/suppliers/receipts/{id}/` по подробному ТЗ: обязательный `Idempotency-Key` (повтор → `replayed: true`), `If-Match`/`version`, `reason` 5–500 + `reason_code`, `dry_run`, `lines` (старое `items` понимаем), `update_product_purchase_price`, `supplier_id`, `payment`, `source`, `device`. Ответ `{receipt, deltas, movements, warnings, replayed}`. Коды по таблице 3.2 через ApiError (`{code, detail, data}`): 412/409 version_conflict, 423 period_closed, построчный has_returns, receipt_fully_returned, negative_stock с min_qty, debt_already_paid, 422 validation_error/fractional_not_allowed.
- Остатки — движение `receipt_correction` на каждую строку; закупка в карточке по правилу (удалили последний приход товара — откат к прошлому); оплаченный приход — сторно/доплата в ту же кассу (закрытая смена → основная касса, `shift_closed_money_to_main`); смена поставщика/оплаты — если не было возвратов и оплат долга.
- Версии: `SupplierReceiptVersion`, `GET …/versions/`, `GET …/versions/{n}/`, `POST …/revert/`; лента `GET suppliers/receipts/changes/?since=`, событие `receipt_changed` (лента + WebSocket), Telegram владельцу.
- Право `can_edit_purchase_documents` — по умолчанию только владелец, выдаёт только владелец (в списке сотрудников, форме и профиле — действующее значение). Окно правки `Company.receipt_edit_window` (по умолчанию 24h) в `users/company/`, менять — только владелец.
- Количество строки прихода — numeric(12,3) (дробное только у весовых), в ответах по-прежнему число.
- Миграции: main 0170_receipt_editor_1030, users 0071_company_receipt_edit_window_1030 (лёгкие).

## 30.10.2026 — ТЗ Умару по проверке выкатки (касса)
- №9 электронный чек по QR: `POST/DELETE api/main/pos/sales/{id}/share-link/` (идемпотентно, срок 90 дней, отзыв → 404), страница `https://app.nurcrm.kg/r/<token>` без входа (ru/ky/uz/tr/en, 360 px, PDF и печать), `/r/<token>.pdf`; в JSON чека адрес, телефон, кассир, бонусы, статус возврата; `share_url` в продаже; `X-Robots-Tag: noindex`, `/robots.txt`.
- №10 возврат со скидкой: у строки продажи `refundable_quantity`, `refundable_amount`, `unit_refund_price`; в ответе возврата `refund.lines`; новая касса при превышении — `refund_exceeds_paid` с `{line_id, max_quantity, max_amount}`. Расчёт — `apps/main/refund_calc.py`. Отказы 001916/001909 были до выкатки Н-02 (29.10).
- №11 чек из очереди при нулевом остатке: `allow_negative_stock: true` в `pos/checkout/` → продажа в минус и `stock_negative: [{product_id, variant_id, balance}]`.
- «Поступления»: `suppliers/receipts/?product_id=`; у прихода `number`, `document_number`, `document_date`, `created_by`, `attachments[]`, `file`; у строки `batch_id`, `batch_number`, `batch_remaining`; `POST/DELETE suppliers/receipts/{id}/file/` (xlsx, xls, PDF, фото).
- Миграции main 0160–0162 (0162 — номера старых приходов, на боевой с lock_timeout).
- Файлы: apps/main/{receipt_share,refund_calc,receipt_files}.py, apps/main/{models,media_receipts,pos_views,pos_serializers,kassa_views,views,serializers,urls}.py, core/{urls,settings}.py.

## 27.10.2026 — Б-52…Б-77, Б-87 (слиты куски помощников)
- Хозмаг: Б-52 дробное количество, unit_code, шаг и минимум (проверки под флагом hardware_2026_11); Б-53 единицы продажи sale_units (штрихкод, цена, коэффициент; продажа, возврат, приход, витрина); Б-54 public/sphere-profiles/ с профилем hardware; Б-55 уровни цен, цены по объёму, цена клиента (только новая касса + флаг); Б-56 прораб: лимит долга (409 credit_limit_exceeded под флагом), объекты; Б-57 атрибуты и фильтр attr.*; Б-58 ячейка хранения по филиалу; Б-59 сопутствующие и аналоги; Б-60 заказ покупателя (резерв, предоплата не выручка, выдача, отмена); Б-61 партии с оттенком и отрезной товар.
- Голос и персонал: Б-62 задачи (приоритет, напоминание, отчёт, фильтры, summary, права исполнителя под is_strict); Б-63 штрафы/премии без денег, сменная ставка, market-salary/statement/; Б-64 график смен и табель; Б-65 журнал действий ИИ ai-actions/; Б-66 отчёт stock_health.
- Мобилка ↔ касса: Б-67 source/device_key/created_by у продажи и возврата; Б-68 updated_after, sold_at, ETag/304; Б-69 задания печати (claim/done/fail, аренда 60 с); Б-70 устройства компании и push-токены; Б-71 отложенные чеки; Б-72 сеансы телефона-сканера.
- Ящик «Чаты» (apps/inbox): Б-73 каналы (секреты AES-GCM, только запись), Б-74 контакты и автосвязь с клиентом, согласия, СТОП; Б-75 диалоги и сообщения; Б-76 единый вебхук с подписью, дедупликация, очередь, запись серверного бота; Б-77 unread-count, ETag, события, push через сменяемый провайдер (по умолчанию журнал); Б-87 неофициальные каналы — только с подтверждением риска, без рассылок и ИИ-auto.
- Зачем: единое ТЗ бэкенду от команды кассы 26.10.2026, разделы 8–11. Всё добавочно: без новых полей в запросе старые кассы работают как раньше.
- Файлы: apps/main/tz26/** (куски hw_units, hw_prices, hw_catalog, hw_batches, cust_orders, staff, ai_stock, pos_sync, pos_print), apps/inbox/**; крючки — apps/main/{serializers,pos_views,kassa_views,pos_bulk,pos_serializers,pos_utils,views,inventory_views,purchase_orders,analytics_market,market_salary_views}.py, apps/main/showcase/*, apps/main/telegram_bot/{tasks,services/telegram_api}.py, apps/possync/views.py, apps/integrations/{idempotency,events}.py, core/settings.py (Celery).
- Второй заход «Чатов» (Б-78…Б-86) — в ветке feature/tz26-b52-b87--inbox2 (WIP 72082fb, 67/73 тестов), не слит.

## 27.10.2026 — каркас Б-52…Б-87
- Что: общие поля новых пунктов в существующих моделях (Product, CartItem, SaleItem, Sale, Client, Task), пакет `apps/main/tz26/` (куски hw_units, hw_prices, hw_catalog, cust_orders, staff, ai_stock, pos_sync, pos_print), новое приложение `apps/inbox` («Чаты»), подключение адресов (`api/main/…`, `api/users/…`, `api/public/…`, `api/main/inbox/…`, `api/inbox/…`).
- Зачем: чтобы куски ТЗ делались параллельно и не правили одни и те же файлы. Все новые поля необязательные — старые ответы API не меняются.
- Файлы: apps/main/models.py, apps/main/urls.py, core/urls.py, core/settings.py, apps/main/tz26/**, apps/inbox/**.
- Миграции — одной пачкой после слияния кусков.
# CHANGELOG (серверная ветка NurCRM)

## 2026-10-27 — fix/server-bugs-2026-10-27 (поверх fix/price-sync-2026-10-27)
Срочные баги, которые нашла касса (Бекназар), документ «ТЗ Умару — СРОЧНО баг сервера».
- GET main/products/list/?ordering=-updated_at (и updated_at) теперь сортирует по времени изменения. Раньше избранные товары всегда шли первыми, и «версия каталога» кассы (page_size=1) не менялась. Файл: apps/main/views.py (ProductListView.filter_queryset). Тест: apps/main/tests_products_ordering_2026_10_27.py.
- Возврат строками у чека со скидкой на чек учитывает долю этой скидки (чек 4,00 со скидкой 0,40 → возврат 3,60, а не 4,00). Сумма всех возвратов не больше оплаченного, последний возврат — ровно остаток. В ответе возврата новое поле refund, у повтора replayed: true. Повторный возврат полностью возвращённого чека: 400 c code refund_exceeds_paid (статус прежний, чтобы старые кассы не сломались). Перенесено из ТЗ Н-02 (fdd6391). Файлы: apps/main/pos_views.py, apps/main/tests_tz_n02_return_discount.py.
- GET main/pos/sales/?page=<за концом> отвечает 200 с пустым results и next: null вместо 500. Перенесено из ТЗ Н-28 (d65a917). Файлы: apps/main/views.py (SupplierReceiptLimitPagination), apps/main/tests_tz_n28_sales_pages.py.
- Не сделано: аванс в clients/{id}/kpis ждёт формулу от программы владельца.
