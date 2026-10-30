from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("main", "0160_salereceiptlink_expires_revoked"),
    ]

    operations = [
        migrations.AddField(
            model_name="supplierreceipt",
            name="number",
            field=models.PositiveIntegerField(blank=True, db_index=True, null=True),
        ),
        migrations.AddField(
            model_name="supplierreceipt",
            name="document_number",
            field=models.CharField(blank=True, db_default="", default="", max_length=64),
        ),
        migrations.AddField(
            model_name="supplierreceipt",
            name="document_date",
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="supplierreceipt",
            name="attachments",
            field=models.ManyToManyField(blank=True, related_name="supplier_receipts", to="main.mainmedia"),
        ),
    ]
