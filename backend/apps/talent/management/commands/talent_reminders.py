from django.core.management.base import BaseCommand

from apps.talent import services


class Command(BaseCommand):
    help = "Rivojlanish rejasi eslatmalari: muddati yaqin va o'tgan maqsadlar, mentorsiz iqtidorlar (har kuni)"

    def handle(self, *args, **options):
        stats = services.send_reminders()
        self.stdout.write(
            self.style.SUCCESS(
                f"Yaqinlashgan: {stats['soon']}, muddati o'tgan: {stats['overdue']}, mentorsiz: {stats['unattended']}"
            )
        )
