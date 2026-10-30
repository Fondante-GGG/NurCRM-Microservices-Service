"""ТЗ 30.10: номера старых приходов — по порядку создания внутри компании.

Отдельная миграция: на боевой базе её можно повторить с lock_timeout, не трогая 0161.
"""
from django.db import migrations

SQL = """
UPDATE main_supplierreceipt r
   SET number = x.rn
  FROM (SELECT id, row_number() OVER (PARTITION BY company_id ORDER BY created_at, id) AS rn
          FROM main_supplierreceipt) x
 WHERE r.id = x.id AND r.number IS NULL
"""


def backfill(apps, schema_editor):
    if schema_editor.connection.vendor == "postgresql":
        schema_editor.execute(SQL)
        return
    SupplierReceipt = apps.get_model("main", "SupplierReceipt")
    seq = {}
    for r in SupplierReceipt.objects.order_by("company_id", "created_at", "id").only("id", "company_id"):
        seq[r.company_id] = seq.get(r.company_id, 0) + 1
        SupplierReceipt.objects.filter(pk=r.pk).update(number=seq[r.company_id])


class Migration(migrations.Migration):

    dependencies = [
        ("main", "0161_supplierreceipt_number_document_attachments"),
    ]

    operations = [
        migrations.RunPython(backfill, migrations.RunPython.noop),
    ]
