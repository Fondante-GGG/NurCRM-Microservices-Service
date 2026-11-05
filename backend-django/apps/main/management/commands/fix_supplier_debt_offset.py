"""
ТЗ кассы 05.11 п.1: исправить долги поставщиков, испорченные «возвратом поставщику» способом debt_offset.

До исправления зачёт писался в prepayment сделки-долга (а payables показывает prepayment как переплату),
и для прихода без сделки уходил на чужой, самый старый долг поставщика.

Что делает команда (по каждому поставщику с возвратами debt_offset начиная с --since):
  бюджет = сумма этих возвратов; сделки-долги приходов ([receipt:…]) с prepayment > 0, от старых к новым:
  x = min(prepayment, остаток бюджета);
  - сделка прихода, из которого был возврат: amount −= x и prepayment −= x (долг остаётся уменьшенным, переплаты нет);
  - чужая сделка: prepayment −= x (её долг возвращается как был).
  Сделки с платежами не трогаются — выводятся для ручной проверки.
  Долг прихода без сделки после выкатки считается сам (_receipt_pay_info вычитает возвраты debt_offset).

Запуск:
  python manage.py fix_supplier_debt_offset                 # только показать (dry-run)
  python manage.py fix_supplier_debt_offset --apply         # записать
  python manage.py fix_supplier_debt_offset --company-id <uuid> --since 2026-10-31
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.main.models import ClientDeal, SupplierReturn, SupplierReturnItem

Q2 = Decimal("0.01")


class Command(BaseCommand):
    help = "Исправить долги поставщиков после возвратов debt_offset (ТЗ 05.11 п.1). По умолчанию dry-run."

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true")
        parser.add_argument("--company-id", default=None)
        parser.add_argument("--since", default="2026-10-31", help="Возвраты с этой даты (ГГГГ-ММ-ДД).")

    def handle(self, *args, **opts):
        apply = opts["apply"]
        since = date.fromisoformat(opts["since"])
        rets = SupplierReturn.objects.filter(
            compensation=SupplierReturn.Compensation.DEBT_OFFSET,
            status=SupplierReturn.Status.POSTED,
            created_at__date__gte=since,
        )
        if opts["company_id"]:
            rets = rets.filter(company_id=opts["company_id"])

        by_supplier = {}
        for r in rets.order_by("created_at"):
            amount = sum(
                (Decimal(str(q)) * Decimal(str(p)) for q, p in
                 SupplierReturnItem.objects.filter(supplier_return=r).values_list("qty", "purchase_price")),
                Decimal("0"),
            ).quantize(Q2)
            rids = {str(r.receipt_id)} if r.receipt_id else set()
            rids |= {str(x) for x in r.items.exclude(receipt_item=None).values_list("receipt_item__receipt_id", flat=True)}
            s = by_supplier.setdefault((r.company_id, r.supplier_id), {"budget": Decimal("0"), "receipts": set(), "returns": []})
            s["budget"] += amount
            s["receipts"] |= rids
            s["returns"].append(f"ВП-{r.number} {amount}")

        changed = skipped = 0
        for (company_id, supplier_id), s in by_supplier.items():
            self.stdout.write(f"Поставщик {supplier_id} (компания {company_id}): возвраты {', '.join(s['returns'])}; бюджет {s['budget']}")
            left = s["budget"]
            with transaction.atomic():
                deals = (
                    ClientDeal.objects.select_for_update()
                    .filter(company_id=company_id, client_id=supplier_id, kind=ClientDeal.Kind.DEBT,
                            prepayment__gt=0, note__contains="[receipt:")
                    .order_by("created_at")
                )
                for deal in deals:
                    if left <= 0:
                        break
                    x = min(deal.prepayment, left)
                    own = any(f"[receipt:{rid}]" in (deal.note or "") for rid in s["receipts"])
                    action = (
                        f"amount {deal.amount}→{deal.amount - x}, prepayment {deal.prepayment}→{deal.prepayment - x}"
                        if own else f"prepayment {deal.prepayment}→{deal.prepayment - x} (чужой долг вернуть)"
                    )
                    if deal.payments.exists() or deal.paid_total > 0:
                        self.stdout.write(f"  ПРОПУСК (есть платежи, вручную): сделка {deal.id}: {action}")
                        skipped += 1
                        left -= x
                        continue
                    self.stdout.write(f"  сделка {deal.id}: {action}")
                    if apply:
                        deal.prepayment = deal.prepayment - x
                        if own:
                            deal.amount = deal.amount - x
                        deal.save()
                    changed += 1
                    left -= x
                if left > 0:
                    self.stdout.write(f"  остаток бюджета {left} — не найден в prepayment (уже чисто или приход без сделки)")
        mode = "ЗАПИСАНО" if apply else "dry-run (ничего не записано)"
        self.stdout.write(self.style.SUCCESS(f"{mode}: сделок {changed}, пропущено {skipped}"))
