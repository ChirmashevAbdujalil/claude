from django.apps import AppConfig


class AuditConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.audit"
    verbose_name = "Harakatlar jurnali"

    def ready(self):
        from . import signals

        signals.connect()
