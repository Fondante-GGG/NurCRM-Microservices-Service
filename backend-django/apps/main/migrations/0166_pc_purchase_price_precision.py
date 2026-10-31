# ТЗ 31.10 п.19: цена закупки с 4 знаками, сумма строки прихода по накладной, остатки ревизии с 3 знаками.
#
# Большие таблицы (main_product ~400 МБ, main_saleitem ~450 МБ) НЕ переписываются: на Postgres колонку
# переводим в numeric без ограничения точности — numeric(p,s) → numeric не требует перезаписи таблицы
# и индексов (меняется только каталог, нужна короткая ACCESS EXCLUSIVE блокировка — выкатывать с
# SET lock_timeout). Округление до 4 знаков делает Django (PreciseDecimalField). В состоянии миграций
# это обычный DecimalField(14, 4).
# Маленькие таблицы (строки приходов/возвратов, журнал закупок, акты ревизии — тысячи строк)
# меняются обычным ALTER COLUMN TYPE numeric(…) — перезапись за доли секунды.
from decimal import Decimal

from django.db import migrations, models

_UNBOUNDED = (
    ("main_product", "purchase_price"),
    ("main_saleitem", "purchase_price_snapshot"),
)


def _to_unbounded_numeric(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return  # SQLite (тесты): точность колонки не хранится
    for table, column in _UNBOUNDED:
        schema_editor.execute(f'ALTER TABLE "{table}" ALTER COLUMN "{column}" TYPE numeric')


class Migration(migrations.Migration):

    dependencies = [
        ("main", "0163_product_protect_supplier_docs"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunPython(_to_unbounded_numeric, migrations.RunPython.noop),
            ],
            state_operations=[
                migrations.AlterField(
                    model_name="product",
                    name="purchase_price",
                    field=models.DecimalField(
                        decimal_places=4,
                        default=0,
                        help_text=(
                            "За одну учётную единицу товара (как в поле «Количество/Остаток» и unit). "
                            "Если остаток в пачках и заведена упаковка ProductPackage для поштучной продажи "
                            "(например сигареты), закупка указывается за пачку; закупка за штуку на кассе = закупка пачки / quantity_in_package."
                        ),
                        max_digits=14,
                        verbose_name="Цена закупки",
                    ),
                ),
                migrations.AlterField(
                    model_name="saleitem",
                    name="purchase_price_snapshot",
                    field=models.DecimalField(
                        blank=True, decimal_places=4, default=None, max_digits=14, null=True,
                        verbose_name="Себестоимость (снапшот)",
                    ),
                ),
            ],
        ),
        migrations.AlterField(
            model_name="supplierreceiptitem",
            name="purchase_price",
            field=models.DecimalField(blank=True, decimal_places=4, max_digits=14, null=True),
        ),
        migrations.AddField(
            model_name="supplierreceiptitem",
            name="line_total",
            field=models.DecimalField(blank=True, decimal_places=4, max_digits=16, null=True),
        ),
        migrations.AlterField(
            model_name="supplierreturnitem",
            name="purchase_price",
            field=models.DecimalField(blank=True, decimal_places=4, max_digits=14, null=True),
        ),
        migrations.AlterField(
            model_name="supplierpurchase",
            name="unit_price",
            field=models.DecimalField(decimal_places=4, default=Decimal("0.00"), max_digits=14, verbose_name="Цена за единицу"),
        ),
        migrations.AlterField(
            model_name="productinventoryitem",
            name="quantity_before",
            field=models.DecimalField(blank=True, decimal_places=3, max_digits=12, null=True, verbose_name="Было на момент проведения"),
        ),
        migrations.AlterField(
            model_name="productinventoryitem",
            name="quantity_fact",
            field=models.DecimalField(decimal_places=3, max_digits=12, verbose_name="Учётное количество (факт)"),
        ),
    ]
