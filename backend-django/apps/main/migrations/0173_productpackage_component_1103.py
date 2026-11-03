# G8 (аудит 03.11): ProductPackage.component — товар состава комплекта (раньше только название).
# main_productpackage маленькая (~600 строк на бою). Колонка uuid NULL без значения по умолчанию и без внешнего
# ключа в базе (db_constraint=False): не нужна блокировка main_product. Индекс на маленькой таблице — мгновенно.
# Запускать с DB_PORT=5432 PGOPTIONS="-c lock_timeout=1s" и повторами (проверено 03.11 на PG 18.6: при 5s запись ждёт до 5 с за долгим отчётом).
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("main", "0172_productimage_thumb_1103"),
    ]

    operations = [
        migrations.AddField(
            model_name="productpackage",
            name="component",
            field=models.ForeignKey(
                blank=True, db_constraint=False, null=True, on_delete=django.db.models.deletion.SET_NULL,
                related_name="+", to="main.product", verbose_name="Товар состава (комплект)",
            ),
        ),
    ]
