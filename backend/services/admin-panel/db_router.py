class MultiDatabaseRouter:
    """
    Routes database operations to specific schema aliases based on app_label.
    Supports eventual extraction of services into separate DB instances by changing DSN.
    """

    route_app_labels = {
        "admin_auth": "auth_db",
        "admin_catalog": "catalog_db",
        "admin_clients": "clients_db",
        "admin_schedule": "schedule_db",
        "admin_booking": "booking_db",
        "admin_finance": "finance_db",
        "admin_audit": "default",
    }

    def db_for_read(self, model, **hints):
        if model._meta.app_label in self.route_app_labels:
            return self.route_app_labels[model._meta.app_label]
        return "default"

    def db_for_write(self, model, **hints):
        if model._meta.app_label in self.route_app_labels:
            return self.route_app_labels[model._meta.app_label]
        return "default"

    def allow_relation(self, obj1, obj2, **hints):
        django_apps = {"auth", "contenttypes", "admin", "sessions"}
        if obj1._meta.app_label in django_apps and obj2._meta.app_label in django_apps:
            return True
        # Strict rule: no relations between different service schemas
        if obj1._meta.app_label != obj2._meta.app_label:
            return False
        return True

    def allow_migrate(self, db, app_label, model_name=None, **hints):
        # Admin panel models are unmanaged; migrations run by individual services
        if app_label in self.route_app_labels and app_label != "admin_audit":
            return False
        return db == "default"
