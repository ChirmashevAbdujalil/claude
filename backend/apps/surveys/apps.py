from django.apps import AppConfig


class SurveysConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.surveys"
    verbose_name = "So'rovnomalar"

    def ready(self):
        from django.contrib.auth.signals import user_logged_in

        def first_login(sender, request, user, **kwargs):
            from .accounts import on_login

            on_login(user)

        user_logged_in.connect(first_login, dispatch_uid="surveys:first-login", weak=False)
