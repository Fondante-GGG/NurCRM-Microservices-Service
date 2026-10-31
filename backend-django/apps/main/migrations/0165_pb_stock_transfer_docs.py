# ТЗ 31.10 п.22: номер документа и файлы у перемещения товара (MarketStockTransfer)
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("main", "0163_product_protect_supplier_docs"),
    ]

    operations = [
        migrations.AddField(
            model_name="marketstocktransfer",
            name="document_number",
            field=models.CharField(blank=True, default="", max_length=64),
        ),
        migrations.AddField(
            model_name="marketstocktransfer",
            name="attachments",
            field=models.ManyToManyField(blank=True, related_name="market_stock_transfers", to="main.mainmedia"),
        ),
    ]
