# ТЗ редактор накладных 30.10.
# supplierreceipt (~1,5 тыс. строк): ADD COLUMN с db_default / NULL — без перезаписи.
# supplierreceiptitem.qty integer -> numeric(12,3): перезапись маленькой таблицы (~2,7 тыс. строк), секунды.
# stockmovement.type — только choices (в базе ничего не меняется). Новая таблица версий прихода.

import django.db.models.deletion
import django.utils.timezone
import uuid
from decimal import Decimal
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('main', '0169_merge_1031'),
        ('users', '0071_company_receipt_edit_window_1030'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name='supplierreceipt',
            name='edit_count',
            field=models.PositiveIntegerField(db_default=0, default=0),
        ),
        migrations.AddField(
            model_name='supplierreceipt',
            name='edited_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='supplierreceipt',
            name='edited_by',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='edited_supplier_receipts', to=settings.AUTH_USER_MODEL),
        ),
        migrations.AlterField(
            model_name='stockmovement',
            name='type',
            field=models.CharField(choices=[('income', 'Приход'), ('expense', 'Расход'), ('transfer', 'Перемещение'), ('return', 'Возврат'), ('writeoff', 'Списание'), ('inventory', 'Инвентаризация'), ('adjustment', 'Корректировка'), ('agent_transfer', 'Передача агенту'), ('agent_return', 'Возврат от агента'), ('staff_transfer', 'Передача между сотрудниками'), ('staff_return', 'Возврат между сотрудниками'), ('receipt_correction', 'Правка прихода')], db_index=True, max_length=24, verbose_name='Тип операции'),
        ),
        migrations.AlterField(
            model_name='supplierreceiptitem',
            name='qty',
            field=models.DecimalField(decimal_places=3, max_digits=12),
        ),
        migrations.CreateModel(
            name='SupplierReceiptVersion',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('version', models.PositiveIntegerField()),
                ('action', models.CharField(blank=True, default='', max_length=16)),
                ('at', models.DateTimeField(db_index=True, default=django.utils.timezone.now)),
                ('device', models.CharField(blank=True, default='', max_length=128)),
                ('source', models.CharField(blank=True, default='', max_length=16)),
                ('reason', models.CharField(blank=True, default='', max_length=500)),
                ('reason_code', models.CharField(blank=True, default='', max_length=32)),
                ('total', models.DecimalField(decimal_places=2, default=Decimal('0.00'), max_digits=16)),
                ('snapshot', models.JSONField(blank=True, default=dict)),
                ('lines_diff', models.JSONField(blank=True, default=list)),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='+', to='users.company')),
                ('receipt', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='versions', to='main.supplierreceipt')),
                ('user', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Версия прихода',
                'verbose_name_plural': 'Версии приходов',
                'ordering': ['receipt', 'version'],
                'indexes': [models.Index(fields=['company', 'at'], name='sup_rcpt_ver_company_at')],
                'constraints': [models.UniqueConstraint(fields=('receipt', 'version'), name='uniq_supplier_receipt_version')],
            },
        ),
    ]
