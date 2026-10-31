# События NurCRM: лента `main/changes`, WebSocket `ws/main/events/`, вебхуки

ТЗ 31.10 п.14. Словарь в коде: `apps/main/event_names.py` (единые имена и соответствие старым).

## Единое имя события

| Единое имя (`event` / `type` потока) | Имя в ленте `main/changes` (`type`) | Когда |
|---|---|---|
| `price_changed` | `product_changed` + `data.what = "price"` | изменилась цена или оптовая цена товара |
| `product_changed` | `product_changed` (`what`: created, deleted, promo, barcode, variants) | товар создан/удалён/изменён |
| `stock_changed` | `stock_changed` (и `product_changed` + `what = "quantity"`) | изменился остаток |
| `sale_created` | `sale_paid` | чек оплачен |
| `sale_changed` | `sale_returned` | по чеку возврат |
| `shift_changed` | `shift_opened`, `shift_closed`, `cash_moved` | смена открыта/закрыта, внесение/изъятие (`state`) |
| `debt_changed` | `debt_created`, `debt_paid` | долг клиента создан/погашен |
| `supplier_debt_changed` | `supplier_debt_changed` | долг поставщику изменился: приход, оплата долга поставщику, возврат поставщику с зачётом |
| `client_changed` | `client_changed` | клиент создан/изменён/удалён |
| `bonus_changed` | `bonus_changed` | бонусная операция |
| `staff_changed` | `staff_changed` | сотрудник изменён (роль, права) |
| `settings_changed` | `app_settings_changed` | настройки приложения (`app`, `keys[]`) |
| `license_changed` | `features_changed` | включены/выключены модули |

Остальные типы ленты (rental_*, pos_request_changed, print_job_created, scanner_scan, customer_order_ready,
task.*, stock.low, order.created, appointment.created, company.updated) в поток WebSocket не попадают, единое имя
у них совпадает с именем ленты.

## Как сопоставляются имена (совместимость)

Старые имена не убраны, добавлены поля:

* `GET /api/main/changes/` — в каждом событии `type` (старое имя ленты, не изменилось) и **новое поле `event`**
  (единое имя). Фильтр `?types=` принимает и старые, и единые имена (`price_changed` разворачивается в
  `product_changed`, потом клиент фильтрует по `event`).
* `ws/main/events/` — `type` уже единое имя (как было); **новое поле `feed_type`** — имя этого же события в ленте.
* `ws/company/` — `event.type` старое имя ленты, **новое `event.event`** — единое имя.

Клиенту достаточно читать поле `event` в ленте и `type` в потоке: имена одинаковые.

## supplier_debt_changed

Приходит и в ленту, и в поток WebSocket (раньше только в ленту). Поля: `ids: [<id поставщика>]`, `supplier`.
Источники: создание прихода (`suppliers/<id>/receipt/`), оплата долга поставщику (`clients/<id>/pay-supplier-debt/`), возврат поставщику с зачётом в долг (`suppliers/<id>/returns/`, `compensation = debt_offset`).

## sale_paid и sale_created

Это одно событие: в ленте `sale_paid`, в потоке и в едином словаре `sale_created`
(`sale_id`, `cashbox`, `shift`). Возврат — `sale_returned` / `sale_changed`.
