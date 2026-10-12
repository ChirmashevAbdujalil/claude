from django.core.management.base import BaseCommand, CommandError

from apps.tenants import plans, services


class Command(BaseCommand):
    help = "Platformaga yangi OTM ulaydi va uning administratori hisobini yaratadi"

    def add_arguments(self, parser):
        parser.add_argument("name", help="OTMning to'liq nomi")
        parser.add_argument("short_name", help="Qisqa nomi, masalan TATU")
        parser.add_argument("--slug", default="", help="Subdomen (bo'sh bo'lsa qisqa nomdan yasaladi)")
        parser.add_argument("--plan", default="pilot", choices=list(plans.PLANS))
        parser.add_argument("--admin", default="", help="Administrator logini (standart: <slug>_admin)")
        parser.add_argument("--email", default="")

    def handle(self, *args, **options):
        try:
            institution, admin, password = services.create_institution(
                name=options["name"],
                short_name=options["short_name"],
                slug=options["slug"],
                plan=options["plan"],
                contact_email=options["email"],
                admin_username=options["admin"],
            )
        except services.TenantError as exc:
            raise CommandError(str(exc)) from exc
        self.stdout.write(self.style.SUCCESS(f"OTM ulandi: {institution} ({institution.plan_info['name']})"))
        self.stdout.write(f"Manzil:  {institution.base_url() or institution.slug + '.localhost:8000'}")
        self.stdout.write(f"Login:   {admin.username}")
        self.stdout.write(f"Parol:   {password}")
        self.stdout.write("Demo ma'lumot kerak bo'lsa: python manage.py seed --demo --institution " + institution.slug)
