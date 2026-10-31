# ТЗ 31.10 п.21: версия прихода (If-Match) и комментарий. Таблица маленькая (~1,5 тыс. строк);
# ADD COLUMN с db_default — без перезаписи (Postgres 11+ хранит значение по умолчанию в каталоге).
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("main", "0167_pc_receipt_numbering_sale_prices"),
    ]

    operations = [
        migrations.AddField(
            model_name="supplierreceipt",
            name="version",
            field=models.PositiveIntegerField(db_default=1, default=1),
        ),
        migrations.AddField(
            model_name="supplierreceipt",
            name="comment",
            field=models.TextField(blank=True, db_default="", default=""),
        ),
    ]
