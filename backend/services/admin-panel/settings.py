import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

SECRET_KEY = os.getenv("SECRET_KEY", "nurcrm-admin-insecure-secret-key-2026")
DEBUG = os.getenv("DEBUG", "True").lower() == "true"
ALLOWED_HOSTS = ["*"]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "backend.services.admin_panel",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "backend.services.admin_panel.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "nurcrm")

def make_db_alias(schema: str, user: str, password: str):
    return {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": DB_NAME,
        "USER": user,
        "PASSWORD": password,
        "HOST": DB_HOST,
        "PORT": DB_PORT,
        "OPTIONS": {"options": f"-c search_path={schema},public"},
    }

DATABASES = {
    "default": make_db_alias("admin", "svc_admin", "svc_admin_secret"),
    "auth_db": make_db_alias("auth", "svc_admin", "svc_admin_secret"),
    "catalog_db": make_db_alias("catalog", "svc_admin", "svc_admin_secret"),
    "clients_db": make_db_alias("clients", "svc_admin", "svc_admin_secret"),
    "schedule_db": make_db_alias("schedule", "svc_admin", "svc_admin_secret"),
    "booking_db": make_db_alias("booking", "svc_admin", "svc_admin_secret"),
    "finance_db": make_db_alias("finance", "svc_admin", "svc_admin_secret"),
}

DATABASE_ROUTERS = ["backend.services.admin_panel.db_router.MultiDatabaseRouter"]

STATIC_URL = "static/"
LANGUAGE_CODE = "ru-ru"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
