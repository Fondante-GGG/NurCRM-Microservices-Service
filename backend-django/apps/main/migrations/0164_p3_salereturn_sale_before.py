# ТЗ 31.10 п.3: снимок чека до возврата (исходный чек в ответе API)

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("main", "0163_product_protect_supplier_docs"),
    ]

    operations = [
        migrations.AddField(
            model_name="salereturn",
            name="sale_before",
            field=models.JSONField(blank=True, null=True, verbose_name="Чек до возврата"),
        ),
    ]
