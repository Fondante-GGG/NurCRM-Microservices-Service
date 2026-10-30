# CHANGELOG бэкенда (ветка feature/tz26-b52-b87)

Новые записи сверху. Единое ТЗ бэкенду 26.10.2026, разделы 8–11 (Б-52…Б-87).

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
