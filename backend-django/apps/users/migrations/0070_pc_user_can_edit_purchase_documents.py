# ТЗ 31.10 п.21: право «Менять: проведённые приходы». users_user ~1,2 тыс. строк, ADD COLUMN NULL — без перезаписи.
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0069_company_finance_closed_until"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="can_edit_purchase_documents",
            field=models.BooleanField(blank=True, default=None, null=True, verbose_name="Менять: проведённые приходы"),
        ),
    ]
