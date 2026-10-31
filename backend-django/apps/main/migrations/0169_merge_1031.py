# 31.10: слияние параллельных веток (п.3 — 0164, п.11–22 — 0165, п.19–21 — 0166…0168).
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("main", "0164_p3_salereturn_sale_before"),
        ("main", "0165_pb_stock_transfer_docs"),
        ("main", "0168_pc_receipt_version"),
    ]

    operations = []
