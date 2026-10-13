from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.audit.context import source as audit_source
from apps.tenants.models import Institution

GRACE_DAYS = 3


class Command(BaseCommand):
    help = "Obuna muddati o'tgan OTMlarni to'xtatadi (har kuni cron bilan ishga tushiring)"

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="Faqat ro'yxatni ko'rsatish")

    def handle(self, *args, **options):
        limit = timezone.localdate() - timedelta(days=GRACE_DAYS)
        expired = list(Institution.objects.filter(is_active=True, paid_until__lt=limit))
        for institution in expired:
            self.stdout.write(f"{institution.short_name}: muddat {institution.paid_until:%d.%m.%Y} da tugagan")
            if not options["dry_run"]:
                institution.is_active = False
                with audit_source("Tizim: obuna nazorati"):
                    institution.save(update_fields=["is_active"])
        self.stdout.write(self.style.SUCCESS(f"Muddati o'tgan OTMlar: {len(expired)}"))
