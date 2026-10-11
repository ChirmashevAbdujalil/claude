"""Telegram botni platformaga ulaydi: webhook va menyu tugmasini sozlaydi.

    python manage.py telegram_setup

Kerakli sozlamalar: TELEGRAM_BOT_TOKEN, TELEGRAM_WEBHOOK_SECRET, SITE_URL (https).
"""

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from apps.notifications import telegram_bot


class Command(BaseCommand):
    help = "Telegram bot webhook va Mini App menyu tugmasini sozlaydi"

    def handle(self, *args, **options):
        site = settings.SITE_URL.rstrip("/")
        if not settings.TELEGRAM_BOT_TOKEN:
            raise CommandError("TELEGRAM_BOT_TOKEN o'rnatilmagan")
        if not settings.TELEGRAM_WEBHOOK_SECRET:
            raise CommandError("TELEGRAM_WEBHOOK_SECRET o'rnatilmagan")
        if not site.startswith("https://"):
            raise CommandError("SITE_URL https:// bilan boshlanishi kerak (Telegram faqat https bilan ishlaydi)")

        webhook = telegram_bot.call(
            "setWebhook",
            {
                "url": f"{site}/telegram/webhook/",
                "secret_token": settings.TELEGRAM_WEBHOOK_SECRET,
                "allowed_updates": ["message"],
            },
        )
        if not (webhook and webhook.get("ok")):
            raise CommandError(f"Webhook o'rnatilmadi: {webhook}")
        self.stdout.write(self.style.SUCCESS(f"Webhook: {site}/telegram/webhook/"))

        menu = telegram_bot.call(
            "setChatMenuButton",
            {"menu_button": {"type": "web_app", "text": "Platforma", "web_app": {"url": f"{site}/app/"}}},
        )
        if menu and menu.get("ok"):
            self.stdout.write(self.style.SUCCESS("Menyu tugmasi: «Platforma» → Mini App"))
        else:
            self.stdout.write(self.style.WARNING(f"Menyu tugmasi o'rnatilmadi: {menu}"))
