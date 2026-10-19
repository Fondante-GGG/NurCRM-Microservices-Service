import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

SECRET_KEY = os.getenv("SECRET_KEY", "nurcrm-admin-insecure-secret-key-2026")
DEBUG = os.getenv("DEBUG", "True").lower() == "true"
ALLOWED_HOSTS = ["*"]

CSRF_TRUSTED_ORIGINS = [
    "https://stage.nurcrm.kg",
    "http://stage.nurcrm.kg",
    "https://stageapp.nurcrm.kg",
    "http://127.0.0.1:8088",
    "http://localhost:8088",
    "http://localhost:8000",
]
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
USE_X_FORWARDED_HOST = True
USE_X_FORWARDED_PORT = True

INSTALLED_APPS = [
    "jazzmin",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "backend.services.admin_panel.apps.AdminAuthConfig",
    "backend.services.admin_panel.apps.AdminCatalogConfig",
    "backend.services.admin_panel.apps.AdminClientsConfig",
    "backend.services.admin_panel.apps.AdminScheduleConfig",
    "backend.services.admin_panel.apps.AdminBookingConfig",
    "backend.services.admin_panel.apps.AdminFinanceConfig",
    "backend.services.admin_panel.apps.AdminAuditConfig",
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
STATICFILES_DIRS = [BASE_DIR / "static"]

LANGUAGE_CODE = "ru-ru"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

JAZZMIN_SETTINGS = {
    "site_title": "KEZEK Admin",
    "site_header": "KEZEK",
    "site_brand": "KEZEK by NurCRM",
    "site_logo": "admin/img/kezek-icon-dark.png",
    "login_logo": "admin/img/kezek-logo-dark.png",
    "site_icon": "admin/img/kezek-icon-dark.png",
    "welcome_sign": "Добро пожаловать в панель управления KEZEK by NurCRM",
    "copyright": "NurCRM KEZEK",
    "search_model": ["admin_auth.AdminCompany", "admin_clients.AdminClient"],
    "user_avatar": None,
    "topmenu_links": [
        {"name": "Главная", "url": "admin:index", "permissions": ["auth.view_user"]},
        {"name": "Перейти в CRM", "url": "https://stage.nurcrm.kg/", "new_window": True},
    ],
    "show_sidebar": True,
    "navigation_expanded": True,
    "order_with_respect_to": ["admin_auth", "admin_catalog", "admin_clients", "admin_schedule", "admin_booking", "admin_finance", "admin_audit"],
    "icons": {
        "admin_auth.AdminCompany": "fas fa-building",
        "admin_auth.AdminEmployee": "fas fa-user-tie",
        "admin_catalog.AdminServiceCategory": "fas fa-folder",
        "admin_catalog.AdminService": "fas fa-cut",
        "admin_clients.AdminClient": "fas fa-users",
        "admin_schedule.AdminAppointment": "fas fa-calendar-check",
        "admin_booking.AdminBookingRequest": "fas fa-clock",
        "admin_finance.AdminCashShift": "fas fa-cash-register",
        "admin_finance.AdminAccrual": "fas fa-money-bill-wave",
        "admin_audit.AuditLogModel": "fas fa-shield-alt",
        "auth.User": "fas fa-user-shield",
        "auth.Group": "fas fa-users-cog",
    },
    "default_icon_parents": "fas fa-chevron-circle-right",
    "default_icon_children": "fas fa-circle",
}

JAZZMIN_UI_TWEAKS = {
    "navbar_small_text": False,
    "footer_small_text": False,
    "body_small_text": False,
    "brand_small_text": False,
    "brand_colour": "navbar-dark",
    "accent": "accent-primary",
    "navbar": "navbar-dark navbar-navy",
    "no_navbar_border": False,
    "navbar_fixed": False,
    "layout_boxed": False,
    "footer_fixed": False,
    "sidebar_fixed": False,
    "sidebar": "sidebar-dark-navy",
    "sidebar_nav_small_text": False,
    "sidebar_disable_expand": False,
    "sidebar_nav_child_indent": False,
    "sidebar_nav_compact_style": False,
    "sidebar_nav_legacy_style": False,
    "sidebar_nav_flat_style": False,
    "theme": "default",
    "dark_mode_theme": None,
    "button_classes": {
        "primary": "btn-primary",
        "secondary": "btn-secondary",
        "info": "btn-info",
        "warning": "btn-warning",
        "danger": "btn-danger",
        "success": "btn-success",
    },
}
