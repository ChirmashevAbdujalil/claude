"""Lokal bazani serverga ko'chirgandan keyin: demo akkauntlarni bloklash, demo so'rovnoma va sessiyalarni tozalash.

Demo akkauntlar o'chirilmaydi, balki kirish imkonsiz qilinadi: ular nomidan yaratilgan challenge, tadbir va
so'rovnomalar saqlanib qoladi.

python manage.py prepare_production            # faqat nima o'chishini ko'rsatadi
python manage.py prepare_production --apply    # o'chiradi
python manage.py prepare_production --apply --clear-responses   # sinov javoblarini ham
"""

from django.contrib.auth.hashers import make_password
from django.contrib.sessions.models import Session
from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import ProtectedError, Q

from apps.accounts.models import User
from apps.surveys.models import Response, Survey
from apps.tenants.context import unscoped

DEMO_PASSWORD_NOTE = "demo akkauntlar bloklanadi (paroli hammaga ma'lum edi: demo12345)"


class Command(BaseCommand):
    help = "Serverga ko'chirilgan bazadan demo va sinov ma'lumotlarini tozalaydi"

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true", help="Haqiqatan o'chirish (bo'lmasa faqat hisobot)")
        parser.add_argument(
            "--clear-responses",
            action="store_true",
            help="Barcha so'rovnoma javoblarini va ular orqali ochilgan talaba akkauntlarini ham o'chirish",
        )

    def handle(self, *args, **options):
        apply, clear = options["apply"], options["clear_responses"]
        with unscoped():
            demo_users = User.objects.filter(pk__in=self._demo_user_ids())
            demo_surveys = Survey.objects.filter(title__endswith="(demo)")
            sessions = Session.objects.all()
            plan = [
                (DEMO_PASSWORD_NOTE, demo_users),
                ("demo so'rovnoma(lar) va ularning javoblari", demo_surveys),
                ("kirish sessiyalari (hamma qayta kiradi)", sessions),
            ]
            if clear:
                survey_students = User.objects.filter(
                    issued_account__isnull=False, role=User.Role.STUDENT, is_superuser=False
                )
                plan += [
                    ("so'rovnoma javoblari (sinov javoblari)", Response.objects.all()),
                    ("so'rovnoma orqali ochilgan talaba akkauntlari", survey_students),
                ]

            self.stdout.write(self.style.MIGRATE_HEADING("Bazadagi so'rovnomalar:"))
            for survey in Survey.objects.order_by("created_at"):
                status = survey.get_status_display()
                self.stdout.write(f"  {survey.responses.count():>6} javob  {survey.title[:70]} ({status})")
            self.stdout.write(self.style.MIGRATE_HEADING("\nO'chiriladigan ma'lumotlar:"))
            for label, queryset in plan:
                self.stdout.write(f"  {queryset.count():>6}  {label}")
            for user in demo_users.order_by("username")[:15]:
                self.stdout.write(f"          · {user.username} ({user.get_role_display()})")

            if not apply:
                self.stdout.write(self.style.WARNING("\nHech narsa o'zgarmadi. O'chirish uchun: --apply qo'shing"))
                return

            with transaction.atomic():
                demo_users.update(is_active=False, password=make_password(None))  # parol yaroqsiz: kirib bo'lmaydi
                for _, queryset in plan[1:]:
                    try:
                        with transaction.atomic():
                            queryset.delete()  # akkaunt bilan uning login-paroli (IssuedAccount) ham o'chadi
                    except ProtectedError:
                        # Boshqa ma'lumot bog'langan akkauntlar o'chirilmaydi, faqat bloklanadi
                        queryset.update(is_active=False, password=make_password(None))

            self.stdout.write(self.style.SUCCESS("\nTozalandi."))
            admins = User.objects.filter(is_active=True).filter(
                Q(is_superuser=True) | Q(role__in=[User.Role.RECTOR, User.Role.ADMIN])
            )
            if admins.exists():
                names = ", ".join(sorted({u.username for u in admins})[:10])
                self.stdout.write(f"Saytga kira oladigan rahbariyat akkauntlari: {names}")
            else:
                self.stdout.write(
                    self.style.WARNING("Rahbariyat akkaunti qolmadi: python manage.py createsuperuser bilan yarating")
                )

    @staticmethod
    def _demo_user_ids():
        """Seed --demo yaratgan akkauntlar: demo_* va <otm>_rector/_teacher/_admin/_studentN, paroli hali demo12345."""
        candidates = User.objects.filter(is_superuser=False).filter(
            Q(username__startswith="demo_") | Q(username__regex=r"_(rector|teacher|admin|student[0-9]*)$")
        )
        return [
            user.pk
            for user in candidates
            if user.username.startswith("demo_") or (user.has_usable_password() and user.check_password("demo12345"))
        ]
