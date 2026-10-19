import sys
import types
from pathlib import Path
from django.apps import AppConfig

BASE_DIR = Path(__file__).resolve().parent

APP_CONFIGS = [
    ("admin_auth", "1. Авторизация и компании"),
    ("admin_catalog", "2. Каталог услуг"),
    ("admin_clients", "3. Клиенты"),
    ("admin_schedule", "4. Расписание и смены"),
    ("admin_booking", "5. Записи"),
    ("admin_finance", "6. Финансы и выплаты"),
    ("admin_audit", "7. Аудит платформы"),
]

for label, verbose in APP_CONFIGS:
    mod_name = f"backend.services.admin_panel.{label}"
    if mod_name not in sys.modules:
        m = types.ModuleType(mod_name)
        sys.modules[mod_name] = m
    else:
        m = sys.modules[mod_name]

    cls_name = "".join(part.capitalize() for part in label.split("_")) + "Config"
    cls = type(
        cls_name,
        (AppConfig,),
        {
            "name": mod_name,
            "label": label,
            "verbose_name": verbose,
            "path": str(BASE_DIR),
        },
    )
    setattr(m, cls_name, cls)
    setattr(sys.modules[__name__], cls_name, cls)
