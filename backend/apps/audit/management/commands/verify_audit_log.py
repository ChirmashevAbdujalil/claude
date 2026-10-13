from django.core.management.base import BaseCommand, CommandError

from apps.audit import services


class Command(BaseCommand):
    help = "Harakatlar jurnali zanjirini tekshiradi: yozuvlar o'zgartirilmagan va o'chirilmaganini"

    def handle(self, *args, **options):
        checked, broken = services.verify(all_institutions=True)
        if broken is not None:
            raise CommandError(f"Jurnal buzilgan: #{broken} yozuvda zanjir uzilgan ({checked} ta yozuv to'g'ri)")
        self.stdout.write(self.style.SUCCESS(f"Jurnal butun: {checked} ta yozuv tekshirildi"))
