from django.apps import AppConfig


class TalentConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.talent"
    verbose_name = "Iqtidorlar bilan ishlash"

    def ready(self):
        from . import signals

        signals.connect()
