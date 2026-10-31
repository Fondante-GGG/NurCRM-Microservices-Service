"""
ТЗ 31.10 п.21: правка проведённого прихода поставщика (редактор накладных).

PATCH /api/main/suppliers/receipts/<uuid>/
  Заголовок If-Match: "<version>" или поле "version" в теле — защита от одновременной правки.
  ?dry_run=1 или "dry_run": true — посчитать и показать изменения, ничего не записывая.
  Тело (всё необязательно):
    "document_number", "document_date" (YYYY-MM-DD или null), "comment",
    "items": [
      {"id": "<строка>", "qty": 5, "purchase_price": "12.3456", "line_total": "61.73"},  — изменить строку
      {"id": "<строка>", "delete": true},                                              — удалить строку
      {"product": "<товар>", "qty": 3, "purchase_price": "10"}                         — добавить строку
    ]  — строки, которых нет в списке, не меняются.

Что пересчитывается в одной транзакции (select_for_update прихода и товаров):
  остатки товаров на разницу количества (и партии/сроки годности строк), закупочная цена товара
  (если это его последний приход), сумма прихода, долг поставщику по сделке с меткой [receipt:<id>],
  version += 1, запись в журнал изменений.

Ошибки ({"code", "detail", ...}):
  403 permission_denied     — нет права can_edit_purchase_documents (владелец — всегда можно)
  409 version_conflict      — If-Match / version не совпали с текущей версией (в ответе current_version)
  409 edit_window_expired   — прошло больше окна правки (настройка компании receipt_edit_window)
  409 period_closed         — дата прихода/накладной в закрытом периоде склада (closed_until)
  409 has_returns           — по приходу есть проведённые возвраты поставщику (менять строки нельзя)
  409 negative_stock        — после правки остаток товара/партии ушёл бы в минус (в ответе products)
  409 debt_already_paid     — сумма долга становится меньше уже оплаченного по сделке
  409 variants_not_supported — у строки товара с вариантами (размер/цвет) нельзя менять количество
  400 item_not_found, items_empty, ошибки полей.

Окно правки: CompanyAppSettings компании (без филиала), программа "nurmarket-mobile",
ключ "receipt_edit_window": "24h" | "48h" | "always", по умолчанию "48h".
"""
from datetime import timedelta
from decimal import Decimal, ROUND_HALF_UP

from django.db import transaction
from django.db.models import F, Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.dateparse import parse_date
from rest_framework import serializers, status
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from apps.main.models import (
    ClientDeal,
    Product,
    ProductVariant,
    SupplierReceipt,
    SupplierReceiptItem,
    SupplierReturn,
)

EDIT_WINDOW_APP = "nurmarket-mobile"
EDIT_WINDOW_KEY = "receipt_edit_window"
EDIT_WINDOWS = {"24h": 24, "48h": 48, "always": None}
DEFAULT_EDIT_WINDOW = "48h"
EDIT_PERMISSION = "can_edit_purchase_documents"

_Q2 = Decimal("0.01")
_Q4 = Decimal("0.0001")


def receipt_edit_window(company_id) -> str:
    from apps.users.models import CompanyAppSettings

    row = CompanyAppSettings.objects.filter(company_id=company_id, branch__isnull=True, app=EDIT_WINDOW_APP).first()
    value = str(((row.settings or {}) if row else {}).get(EDIT_WINDOW_KEY) or "").strip().lower()
    return value if value in EDIT_WINDOWS else DEFAULT_EDIT_WINDOW


def can_edit_purchase_documents(user) -> bool:
    """Владелец — всегда; сотрудник — явное право True; NULL — по умолчанию да только администратору."""
    from apps.warehouse.op_permissions import is_company_owner

    if user is None:
        return False
    if is_company_owner(user):
        return True
    explicit = getattr(user, EDIT_PERMISSION, None)
    if explicit is not None:
        return bool(explicit)
    return (getattr(user, "role", None) or "") == "admin"


def receipt_etag(receipt) -> str:
    return f'"{receipt.version}"'


def _parse_version(raw):
    if raw in (None, ""):
        return None
    s = str(raw).strip()
    if s.startswith("W/"):
        s = s[2:]
    s = s.strip('"').strip()
    if s.lower().startswith("v"):
        s = s[1:]
    try:
        return int(s)
    except (TypeError, ValueError):
        raise ValidationError({"code": "version_invalid", "detail": "If-Match / version — номер версии прихода."})


def _conflict(code, detail, http=status.HTTP_409_CONFLICT, **extra):
    return Response({"code": code, "detail": detail, **extra}, status=http)


def _truthy(raw):
    return raw is True or str(raw).strip().lower() in ("1", "true", "yes", "y", "on")


def _s(v, q=_Q2):
    return None if v is None else f"{Decimal(str(v)).quantize(q, rounding=ROUND_HALF_UP)}"


class _EditLineSerializer(serializers.Serializer):
    id = serializers.UUIDField(required=False, allow_null=True)
    product = serializers.UUIDField(required=False, allow_null=True)
    qty = serializers.IntegerField(min_value=1, required=False)
    purchase_price = serializers.DecimalField(max_digits=14, decimal_places=4, required=False, allow_null=True,
                                              min_value=Decimal("0"))
    line_total = serializers.DecimalField(max_digits=16, decimal_places=4, required=False, allow_null=True,
                                          min_value=Decimal("0"))
    delete = serializers.BooleanField(required=False, default=False)


class _EditSerializer(serializers.Serializer):
    items = _EditLineSerializer(many=True, required=False)
    document_number = serializers.CharField(required=False, allow_blank=True, allow_null=True, max_length=64)
    document_date = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    comment = serializers.CharField(required=False, allow_blank=True, allow_null=True)


def _line_amount(qty, purchase_price, line_total, product):
    """Сумма строки без округления: как в приходе (line_total, иначе qty × закупка, иначе закупка товара)."""
    if line_total is not None:
        return Decimal(str(line_total))
    pp = purchase_price if purchase_price is not None else (getattr(product, "purchase_price", None) or Decimal("0"))
    return Decimal(int(qty)) * Decimal(str(pp))


def patch_receipt(view, request, pk):
    with transaction.atomic():
        return _patch_receipt(view, request, pk)


def _patch_receipt(view, request, pk):
    from apps.construction import audit as admin_audit
    from apps.main.views import _find_receipt_deal, _supplier_debt_total

    user = request.user
    data = request.data if hasattr(request.data, "get") else {}
    dry_run = _truthy(request.query_params.get("dry_run")) or _truthy(data.get("dry_run"))

    qs = view._filter_qs_company_branch(SupplierReceipt.objects.all()).select_for_update()
    receipt = get_object_or_404(qs, pk=pk)
    company = receipt.company

    # 1. право
    if not can_edit_purchase_documents(user):
        return _conflict("permission_denied", "Недостаточно прав: правка документов закупки.", http=status.HTTP_403_FORBIDDEN)

    # 2. версия: If-Match или version в теле
    expected = _parse_version(request.headers.get("If-Match"))
    if expected is None:
        expected = _parse_version(data.get("version"))
    if expected is not None and expected != receipt.version:
        return _conflict("version_conflict", "Приход уже изменён другим пользователем. Обновите и повторите.",
                         current_version=receipt.version)

    # 3. окно правки
    window = receipt_edit_window(company.id)
    hours = EDIT_WINDOWS[window]
    if hours is not None and receipt.created_at and timezone.now() - receipt.created_at > timedelta(hours=hours):
        return _conflict("edit_window_expired", f"Приход можно менять только {hours} ч после проведения.",
                         edit_window=window)

    ser = _EditSerializer(data=data)
    ser.is_valid(raise_exception=True)
    vd = ser.validated_data

    header = {}
    if "document_number" in vd:
        header["document_number"] = str(vd["document_number"] or "").strip()[:64]
    if "document_date" in vd:
        raw = vd["document_date"]
        if raw in (None, ""):
            header["document_date"] = None
        else:
            d = parse_date(str(raw)[:10])
            if d is None:
                raise ValidationError({"document_date": "Дата накладной: YYYY-MM-DD."})
            header["document_date"] = d
    if "comment" in vd:
        header["comment"] = str(vd["comment"] or "")

    # 4. закрытый период склада (дата проведения, старая и новая дата накладной)
    from apps.warehouse.op_permissions import BusinessRuleError
    from apps.warehouse.services import ensure_period_open

    try:
        ensure_period_open(
            company=company, user=user,
            dates=[receipt.created_at, receipt.document_date, header.get("document_date")],
        )
    except BusinessRuleError as exc:
        return _conflict(exc.api_code, str(exc), **exc.extra)

    rows = vd.get("items") or []
    # 5. возвраты поставщику по приходу — строки не меняем
    if rows:
        has_returns = SupplierReturn.objects.filter(status=SupplierReturn.Status.POSTED).filter(
            Q(receipt=receipt) | Q(items__receipt_item__receipt=receipt)
        ).exists()
        if has_returns:
            return _conflict("has_returns", "По приходу есть возвраты поставщику — строки менять нельзя.")

    # 6. план изменений строк
    current = {str(i.id): i for i in receipt.items.select_related("product").order_by("id")}
    plan = []  # dict(action, item, product, qty, purchase_price, line_total)
    touched = set()
    for idx, row in enumerate(rows):
        rid = row.get("id")
        if rid:
            item = current.get(str(rid))
            if item is None or str(rid) in touched:
                raise ValidationError({"code": "item_not_found", "detail": f"Строка {idx + 1}: нет такой строки в приходе."})
            touched.add(str(rid))
            if row.get("delete"):
                plan.append({"action": "delete", "item": item, "product_id": item.product_id})
                continue
            pp = row["purchase_price"] if "purchase_price" in row else item.purchase_price
            lt = row["line_total"] if "line_total" in row else item.line_total
            qty = row.get("qty", item.qty)
            if "line_total" in row and lt is not None and "purchase_price" not in row:
                pp = (Decimal(str(lt)) / Decimal(int(qty))).quantize(_Q4, rounding=ROUND_HALF_UP)
            elif "qty" in row and "line_total" not in row and item.line_total is not None and int(qty) != item.qty:
                lt = None  # сумма по накладной относилась к старому количеству — дальше считаем qty × цена
            plan.append({"action": "update", "item": item, "product_id": item.product_id,
                         "qty": int(qty), "purchase_price": pp, "line_total": lt})
        else:
            if not row.get("product") or row.get("delete"):
                raise ValidationError({"code": "item_not_found", "detail": f"Строка {idx + 1}: нужен product (или id строки)."})
            if "qty" not in row:
                raise ValidationError({"items": [f"Строка {idx + 1}: нужен qty."]})
            qty = int(row["qty"])
            pp = row.get("purchase_price")
            lt = row.get("line_total")
            if lt is not None and pp is None:
                pp = (Decimal(str(lt)) / Decimal(qty)).quantize(_Q4, rounding=ROUND_HALF_UP)
            plan.append({"action": "add", "item": None, "product_id": row["product"],
                         "qty": qty, "purchase_price": pp, "line_total": lt})

    deleted = {str(p["item"].id) for p in plan if p["action"] == "delete"}
    added = [p for p in plan if p["action"] == "add"]
    if rows and len(current) - len(deleted) + len(added) <= 0:
        raise ValidationError({"code": "items_empty", "detail": "В приходе должна остаться хотя бы одна строка."})

    product_ids = {p["product_id"] for p in plan}
    prod_qs = view._filter_qs_company_branch(Product.objects.all()).select_for_update()
    products = {p.id: p for p in prod_qs.filter(id__in=product_ids)} if product_ids else {}
    missing = [str(pid) for pid in product_ids if pid not in products]
    if missing:
        raise ValidationError({"items": [f"Товары не найдены/не доступны: {', '.join(missing)}"]})

    # разница количества по товарам и проверка остатков
    stock_delta = {}
    for p in plan:
        old_qty = p["item"].qty if p["item"] is not None else 0
        new_qty = 0 if p["action"] == "delete" else p["qty"]
        p["delta"] = new_qty - old_qty
        if p["delta"]:
            stock_delta[p["product_id"]] = stock_delta.get(p["product_id"], 0) + p["delta"]

    variant_locked = [
        str(pid) for pid, d in stock_delta.items()
        if d and ProductVariant.objects.filter(product_id=pid).exists()
    ]
    if variant_locked:
        return _conflict("variants_not_supported",
                         "У товара есть варианты (размер/цвет): количество строки меняйте возвратом или новым приходом.",
                         products=variant_locked)

    negative = []
    for pid, d in stock_delta.items():
        prod = products[pid]
        before = Decimal(str(prod.quantity or 0))
        if d < 0 and before + d < 0:
            negative.append({"product_id": str(pid), "name": prod.name,
                             "available": _s(before, Decimal("0.001")), "required": _s(-d, Decimal("0.001"))})
    batch_moves = _batch_moves(plan)
    for mv in batch_moves:
        if mv["batch"].remaining + mv["delta"] < 0:
            negative.append({"product_id": str(mv["batch"].product_id), "batch": mv["batch"].label,
                             "available": _s(mv["batch"].remaining, Decimal("0.001")),
                             "required": _s(-mv["delta"], Decimal("0.001"))})
    if negative:
        return _conflict("negative_stock", "Товар уже продан или списан: остаток ушёл бы в минус.", products=negative)

    # суммы прихода
    def _total(lines):
        return sum(lines, Decimal("0")).quantize(_Q2, rounding=ROUND_HALF_UP)

    old_lines = {k: _line_amount(i.qty, i.purchase_price, i.line_total, i.product) for k, i in current.items()}
    new_lines = dict(old_lines)
    for p in plan:
        if p["action"] == "delete":
            new_lines.pop(str(p["item"].id), None)
        elif p["action"] == "update":
            new_lines[str(p["item"].id)] = _line_amount(p["qty"], p["purchase_price"], p["line_total"], products[p["product_id"]])
        else:
            new_lines[f"new-{id(p)}"] = _line_amount(p["qty"], p["purchase_price"], p["line_total"], products[p["product_id"]])
    total_before, total_after = _total(old_lines.values()), _total(new_lines.values())
    diff = total_after - total_before

    # долг поставщику по сделке прихода
    deal = _find_receipt_deal(company, receipt.supplier_id, receipt.id)
    if deal is not None and deal.kind != ClientDeal.Kind.DEBT:
        deal = None
    debt = None
    if deal is not None:
        paid = deal.paid_total
        new_amount = (deal.amount or Decimal("0")) + diff
        prepay = deal.prepayment or Decimal("0")
        debt = {
            "deal_id": str(deal.id),
            "amount_before": _s(deal.amount), "amount_after": _s(new_amount),
            "paid": _s(paid), "prepayment": _s(prepay),
            "remaining_after": _s(new_amount - prepay - paid),
        }
        if diff and (new_amount < prepay or new_amount - prepay < paid):
            return _conflict("debt_already_paid",
                             "По долгу за этот приход уже заплачено больше новой суммы.", debt=debt)

    warnings = []
    if diff and deal is None and _has_cash_payment(receipt):
        warnings.append("cash_payment_not_changed")

    changes = {
        "lines": [_line_change(p, products) for p in plan],
        "stock": [
            {"product_id": str(pid), "name": products[pid].name,
             "quantity_before": _s(products[pid].quantity or 0, Decimal("0.001")),
             "quantity_after": _s(Decimal(str(products[pid].quantity or 0)) + d, Decimal("0.001")),
             "delta": _s(d, Decimal("0.001"))}
            for pid, d in stock_delta.items()
        ],
        "header": {k: (v.isoformat() if hasattr(v, "isoformat") else v) for k, v in header.items()},
        "total_before": _s(total_before), "total_after": _s(total_after), "total_diff": _s(diff),
        "debt": debt,
        "warnings": warnings,
    }

    if dry_run:
        resp = Response({"dry_run": True, "id": str(receipt.id), "version": receipt.version, "changes": changes})
        resp["ETag"] = receipt_etag(receipt)
        return resp

    # ---- запись ----
    before_log = {"version": receipt.version, "total": _s(total_before), **{
        k: (getattr(receipt, k).isoformat() if hasattr(getattr(receipt, k), "isoformat") else getattr(receipt, k))
        for k in header
    }}
    from apps.main.services.product_expiry_batches import receive_stock

    for p in plan:
        prod = products[p["product_id"]]
        if p["action"] == "delete":
            p["item"].delete()
        elif p["action"] == "update":
            item = p["item"]
            item.qty, item.purchase_price, item.line_total = p["qty"], p["purchase_price"], p["line_total"]
            item.save(update_fields=["qty", "purchase_price", "line_total"])
        else:
            p["item"] = SupplierReceiptItem.objects.create(
                receipt=receipt, product=prod, qty=p["qty"], purchase_price=p["purchase_price"],
                line_total=p["line_total"], previous_sale_price=prod.price, sale_price=prod.price,
                markup_percent=prod.markup_percent,
            )
            receive_stock(prod, p["qty"], source_kind="purchase", source_id=receipt.id, user=user)
        if p["action"] != "add" and p["delta"]:
            _adjust_expiry(prod, receipt, p["delta"])

    for mv in batch_moves:
        from apps.main.tz26.hw_batches.models import ProductBatch, ProductBatchReceiptLine

        ProductBatch.objects.filter(pk=mv["batch"].pk).update(
            remaining=F("remaining") + mv["delta"], received_total=F("received_total") + mv["delta"])
        if mv["new_qty"] is not None:
            ProductBatchReceiptLine.objects.filter(pk=mv["line"].pk).update(quantity=mv["new_qty"])

    for pid, d in stock_delta.items():
        Product.objects.filter(pk=pid).update(quantity=F("quantity") + d)

    _apply_purchase_prices(receipt, plan, products)

    if deal is not None and diff:
        _apply_deal_diff(deal, diff)

    for k, v in header.items():
        setattr(receipt, k, v)
    receipt.version = (receipt.version or 0) + 1
    receipt.save(update_fields=[*header.keys(), "version"])

    try:
        admin_audit.log_request(
            request, "update", "supplier_receipt", receipt.id, f"Приход №{receipt.number}",
            before=before_log,
            after={"version": receipt.version, "total": _s(total_after), "lines": changes["lines"],
                   **changes["header"]},
            company=company,
        )
    except Exception:
        pass

    from apps.main.cache_utils import invalidate_cache_pattern
    invalidate_cache_pattern(f"products:list:{company.id}:")
    invalidate_cache_pattern(f"analytics:market:{company.id}:")

    fresh = view._supplier_receipts_base_queryset().get(pk=receipt.pk)
    out = view.get_serializer(fresh).data
    out["lines"] = out.get("items") or []
    out["changes"] = changes
    out["dry_run"] = False
    if deal is not None:
        out["supplier_debt_total"] = f"{_supplier_debt_total(company, receipt.supplier_id):.2f}"
    resp = Response(out)
    resp["ETag"] = receipt_etag(receipt)
    return resp


def _line_change(p, products):
    item = p["item"]
    prod = products[p["product_id"]]
    row = {
        "action": p["action"], "item_id": str(item.id) if item is not None else None,
        "product_id": str(prod.id), "product_name": prod.name,
        "qty_before": item.qty if item is not None else None,
        "qty_after": None if p["action"] == "delete" else p["qty"],
        "purchase_price_before": _s(item.purchase_price, _Q4) if item is not None else None,
        "purchase_price_after": None if p["action"] == "delete" else _s(p["purchase_price"], _Q4),
        "line_total_before": _s(item.line_total) if item is not None else None,
        "line_total_after": None if p["action"] == "delete" else _s(p["line_total"]),
    }
    return row


def _batch_moves(plan):
    """Партии (ТЗ 26.10 Б-61) строк, у которых меняется количество: остаток партии двигается на разницу."""
    try:
        from apps.main.tz26.hw_batches.models import ProductBatchReceiptLine
    except Exception:  # pragma: no cover
        return []
    ids = [p["item"].id for p in plan if p["item"] is not None and p["delta"]]
    if not ids:
        return []
    lines = {
        ln.receipt_item_id: ln
        for ln in ProductBatchReceiptLine.objects.select_related("batch").select_for_update().filter(receipt_item_id__in=ids)
    }
    out = []
    for p in plan:
        ln = lines.get(p["item"].id) if p["item"] is not None else None
        if ln is None:
            continue
        new_qty = None if p["action"] == "delete" else Decimal(p["qty"])
        out.append({"batch": ln.batch, "line": ln, "delta": Decimal(p["delta"]), "new_qty": new_qty})
    return out


def _adjust_expiry(product, receipt, delta):
    """Партия срока годности прихода (best-effort, как consume_stock): остаток на разницу, не ниже 0."""
    from apps.main.models import ProductExpiryBatch

    batch = (
        ProductExpiryBatch.objects.select_for_update()
        .filter(product=product, source_kind="purchase", source_id=str(receipt.id))
        .order_by("received_at").first()
    )
    if batch is None:
        if delta > 0:
            from apps.main.services.product_expiry_batches import receive_stock

            receive_stock(product, delta, source_kind="purchase", source_id=receipt.id)
        return
    d = Decimal(delta)
    batch.quantity = max(Decimal("0"), batch.quantity + d)
    batch.remaining_quantity = max(Decimal("0"), batch.remaining_quantity + d)
    batch.save(update_fields=["quantity", "remaining_quantity"])


def _apply_purchase_prices(receipt, plan, products):
    """Закупка товара = цена строки, если этот приход — последний по товару (иначе цену задал более поздний)."""
    for p in plan:
        if p["action"] == "delete" or p["purchase_price"] is None:
            continue
        prod = products[p["product_id"]]
        later = SupplierReceiptItem.objects.filter(
            product_id=prod.id, receipt__created_at__gt=receipt.created_at
        ).exists()
        if later:
            continue
        new_pp = Decimal(str(p["purchase_price"]))
        if Decimal(str(prod.purchase_price or 0)) == new_pp:
            continue
        upd = {"purchase_price": new_pp}
        price = Decimal(str(prod.price or 0))
        if new_pp > 0 and price > 0:
            upd["markup_percent"] = ((price - new_pp) / new_pp * Decimal("100")).quantize(_Q4, rounding=ROUND_HALF_UP)
        Product.objects.filter(pk=prod.pk).update(**upd)


def _apply_deal_diff(deal, diff):
    """
    Сумма долга по приходу меняется на diff. Без платежей — обычное сохранение (график пересоберётся).
    С платежами график не пересобираем (модель это запрещает): разница ложится на последние
    неоплаченные взносы, остатки balance_after пересчитываются.
    """
    from apps.main.models import DealInstallment

    deal = ClientDeal.objects.select_for_update().get(pk=deal.pk)
    has_payments = deal.payments.exists() or deal.paid_total > 0
    new_amount = (deal.amount or Decimal("0")) + diff
    if not has_payments:
        deal.amount = new_amount
        deal.save()
        return
    ClientDeal.objects.filter(pk=deal.pk).update(amount=new_amount, updated_at=timezone.now())
    insts = list(DealInstallment.objects.select_for_update().filter(deal=deal).order_by("number"))
    if not insts:
        return
    if diff > 0:
        last = insts[-1]
        last.amount = (last.amount or Decimal("0")) + diff
    else:
        left = -diff
        for inst in reversed(insts):
            if left <= 0:
                break
            room = (inst.amount or Decimal("0")) - (inst.paid_amount or Decimal("0"))
            take = min(room, left) if room > 0 else Decimal("0")
            inst.amount -= take
            left -= take
    balance = new_amount - (deal.prepayment or Decimal("0"))
    for inst in insts:
        balance = (balance - inst.amount).quantize(_Q2)
        inst.balance_after = balance
    DealInstallment.objects.bulk_update(insts, ["amount", "balance_after"])


def _has_cash_payment(receipt):
    from apps.construction.models import CashFlow

    return CashFlow.objects.filter(
        source_kind=CashFlow.SourceKind.PROCUREMENT_RECEIPT, source_id=str(receipt.id), type=CashFlow.Type.EXPENSE
    ).exists()
