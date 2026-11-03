# 03.11 front-market: CashFlow.employee — кому выплачена зарплата.
# Таблица construction_cashflow большая (~850 тыс. строк, ~1 ГБ), поэтому на Postgres:
#   - колонка без значения по умолчанию (мгновенно),
#   - внешний ключ NOT VALID (без проверки всей таблицы под блокировкой; колонка пустая),
#   - индекс CONCURRENTLY (не блокирует запись). Миграция atomic = False.
# Запускать с DB_PORT=5432 PGOPTIONS="-c lock_timeout=1s" и повторами (проверено 03.11 на PG 18.6: при 5s запись ждёт до 5 с за долгим отчётом).
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models

FIELD = models.ForeignKey(
    blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
    related_name="paid_cash_flows", to=settings.AUTH_USER_MODEL, verbose_name="Сотрудник (кому выплата)",
)
INDEX = models.Index(fields=["employee", "created_at"], name="ix_flow_employee_created")

PG_FORWARD = [
    "ALTER TABLE construction_cashflow ADD COLUMN IF NOT EXISTS employee_id uuid NULL",
    """DO $$ BEGIN
         IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'construction_cashflow_employee_id_fk_users_user_id') THEN
           ALTER TABLE construction_cashflow ADD CONSTRAINT construction_cashflow_employee_id_fk_users_user_id
             FOREIGN KEY (employee_id) REFERENCES users_user(id) DEFERRABLE INITIALLY DEFERRED NOT VALID;
         END IF;
       END $$""",
]
PG_INDEX = "CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_flow_employee_created ON construction_cashflow (employee_id, created_at)"
PG_BACKWARD = [
    "DROP INDEX CONCURRENTLY IF EXISTS ix_flow_employee_created",
    "ALTER TABLE construction_cashflow DROP COLUMN IF EXISTS employee_id",
]


def _real_model():
    # в database_operations состояние ещё без поля — для не-Postgres берём настоящую модель
    from apps.construction.models import CashFlow

    return CashFlow


def forward(apps, schema_editor):
    if schema_editor.connection.vendor == "postgresql":
        with schema_editor.connection.cursor() as c:
            for sql in PG_FORWARD:
                c.execute(sql)
            # прошлая попытка CONCURRENTLY оборвалась по lock_timeout — остаётся INVALID-индекс: убрать и сделать заново
            c.execute(
                "SELECT i.indisvalid FROM pg_index i JOIN pg_class c ON c.oid = i.indexrelid "
                "WHERE c.relname = 'ix_flow_employee_created'"
            )
            row = c.fetchone()
            if row is not None and not row[0]:
                c.execute("DROP INDEX CONCURRENTLY IF EXISTS ix_flow_employee_created")
            c.execute(PG_INDEX)
        return
    model = _real_model()
    schema_editor.add_field(model, model._meta.get_field("employee"))
    schema_editor.add_index(model, INDEX)


def backward(apps, schema_editor):
    if schema_editor.connection.vendor == "postgresql":
        with schema_editor.connection.cursor() as c:
            for sql in PG_BACKWARD:
                c.execute(sql)
        return
    model = _real_model()
    schema_editor.remove_index(model, INDEX)
    schema_editor.remove_field(model, model._meta.get_field("employee"))


class Migration(migrations.Migration):
    atomic = False

    dependencies = [
        ("construction", "0038_cashflow_kind"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AddField(model_name="cashflow", name="employee", field=FIELD),
                migrations.AddIndex(model_name="cashflow", index=INDEX),
            ],
            database_operations=[migrations.RunPython(forward, backward)],
        ),
    ]
