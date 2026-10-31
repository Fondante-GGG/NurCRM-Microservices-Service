# 31.10: удаление товара больше не стирает строки приходов/возвратов/заказов поставщику (CASCADE -> PROTECT).
# on_delete работает в Python, SQL не меняется.
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("main", "0162_supplierreceipt_number_backfill"),
    ]

    operations = [
        migrations.AlterField(
            model_name="purchaseorderline",
            name="product",
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="purchase_order_lines", to="main.product"),
        ),
        migrations.AlterField(
            model_name="supplierreceiptitem",
            name="product",
            field=models.ForeignKey(db_index=True, on_delete=django.db.models.deletion.PROTECT, related_name="supplier_receipt_items", to="main.product"),
        ),
        migrations.AlterField(
            model_name="supplierreturnitem",
            name="product",
            field=models.ForeignKey(db_index=True, on_delete=django.db.models.deletion.PROTECT, related_name="supplier_return_items", to="main.product"),
        ),
    ]
