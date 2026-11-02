# S6 (аудит 03.11): CashFlow.salary_period_from / salary_period_to — за какой период выплата зарплаты.
# Таблица construction_cashflow большая (~850 тыс. строк), поэтому как 0039:
#   - две колонки date NULL без значения по умолчанию — Postgres меняет только каталог (мгновенно),
#     нужна лишь короткая блокировка таблицы; IF NOT EXISTS — можно повторять;
#   - без индексов (фильтр идёт внутри компании, по уже отобранным строкам);
#   - atomic = False: при lock_timeout откатывается одна команда, повтор продолжает.
# Запускать с DB_PORT=5432 PGOPTIONS="-c lock_timeout=5s" и повторами, как 29.10.
from django.db import migrations, models

PG_FORWARD = [
    "ALTER TABLE construction_cashflow ADD COLUMN IF NOT EXISTS salary_period_from date NULL",
    "ALTER TABLE construction_cashflow ADD COLUMN IF NOT EXISTS salary_period_to date NULL",
]
PG_BACKWARD = [
    "ALTER TABLE construction_cashflow DROP COLUMN IF EXISTS salary_period_to",
    "ALTER TABLE construction_cashflow DROP COLUMN IF EXISTS salary_period_from",
]
NAMES = ("salary_period_from", "salary_period_to")


def _real_model():
    from apps.construction.models import CashFlow

    return CashFlow


def forward(apps, schema_editor):
    if schema_editor.connection.vendor == "postgresql":
        with schema_editor.connection.cursor() as c:
            for sql in PG_FORWARD:
                c.execute(sql)
        return
    model = _real_model()
    for name in NAMES:
        schema_editor.add_field(model, model._meta.get_field(name))


def backward(apps, schema_editor):
    if schema_editor.connection.vendor == "postgresql":
        with schema_editor.connection.cursor() as c:
            for sql in PG_BACKWARD:
                c.execute(sql)
        return
    model = _real_model()
    for name in reversed(NAMES):
        schema_editor.remove_field(model, model._meta.get_field(name))


class Migration(migrations.Migration):
    atomic = False

    dependencies = [
        ("construction", "0039_cashflow_employee_1103"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AddField(model_name="cashflow", name="salary_period_from",
                                    field=models.DateField(blank=True, null=True, verbose_name="Зарплата: период с")),
                migrations.AddField(model_name="cashflow", name="salary_period_to",
                                    field=models.DateField(blank=True, null=True, verbose_name="Зарплата: период по")),
            ],
            database_operations=[migrations.RunPython(forward, backward)],
        ),
    ]
