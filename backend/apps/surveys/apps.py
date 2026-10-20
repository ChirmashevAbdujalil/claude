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

        from django.db import transaction
        from django.db.models.signals import post_delete

        from .models import ResponseFile

        def remove_file(sender, instance, **kwargs):
            # Diskdagi fayl tranzaksiya muvaffaqiyatli tugagandan keyin o'chiriladi
            name, storage = instance.file.name, instance.file.storage
            if name:
                transaction.on_commit(lambda: storage.delete(name))

        post_delete.connect(remove_file, sender=ResponseFile, dispatch_uid="surveys:remove-file", weak=False)
