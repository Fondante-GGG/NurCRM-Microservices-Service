# ТЗ 31.10 п.20: номер возврата поставщику (по компании, как у прихода) и снимок цен продажи в строке прихода.
# Таблицы маленькие (возвратов ~20, строк приходов ~3 тыс.): ADD COLUMN NULL без перезаписи, backfill — один UPDATE.
from django.db import migrations, models

SQL = """
UPDATE main_supplierreturn r
   SET number = x.rn
  FROM (SELECT id, row_number() OVER (PARTITION BY company_id ORDER BY created_at, id) AS rn
          FROM main_supplierreturn) x
 WHERE r.id = x.id AND r.number IS NULL
"""


def backfill(apps, schema_editor):
    if schema_editor.connection.vendor == "postgresql":
        schema_editor.execute(SQL)
        return
    SupplierReturn = apps.get_model("main", "SupplierReturn")
    seq = {}
    for r in SupplierReturn.objects.order_by("company_id", "created_at", "id").only("id", "company_id"):
        seq[r.company_id] = seq.get(r.company_id, 0) + 1
        SupplierReturn.objects.filter(pk=r.pk).update(number=seq[r.company_id])


class Migration(migrations.Migration):

    dependencies = [
        ("main", "0166_pc_purchase_price_precision"),
    ]

    operations = [
        migrations.AddField(
            model_name="supplierreceiptitem",
            name="markup_percent",
            field=models.DecimalField(blank=True, decimal_places=4, max_digits=12, null=True),
        ),
        migrations.AddField(
            model_name="supplierreceiptitem",
            name="sale_price",
            field=models.DecimalField(blank=True, decimal_places=3, max_digits=10, null=True),
        ),
        migrations.AddField(
            model_name="supplierreceiptitem",
            name="previous_sale_price",
            field=models.DecimalField(blank=True, decimal_places=3, max_digits=10, null=True),
        ),
        migrations.AddField(
            model_name="supplierreturn",
            name="number",
            field=models.PositiveIntegerField(blank=True, db_index=True, null=True),
        ),
        migrations.RunPython(backfill, migrations.RunPython.noop),
    ]
