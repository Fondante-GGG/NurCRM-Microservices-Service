# ТЗ редактор накладных 30.10: окно правки приходов на компании. users_company маленькая, ADD COLUMN NULL — без перезаписи.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0070_pc_user_can_edit_purchase_documents'),
    ]

    operations = [
        migrations.AddField(
            model_name='company',
            name='receipt_edit_window',
            field=models.CharField(blank=True, max_length=8, null=True, verbose_name='Окно правки приходов'),
        ),
    ]
