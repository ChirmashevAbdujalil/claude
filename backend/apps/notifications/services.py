"""Bildirishnomalar: saytda saqlanadi va (ulangan bo'lsa) Telegram orqali yuboriladi."""

import logging
import threading

from django.db import transaction

from . import telegram_bot
from .models import Notification

logger = logging.getLogger(__name__)

# Testlarda Telegram'ga yuborishni sinxron qilish uchun almashtiriladi
_run_in_background = True


def _deliver_to_telegram(chat_id: int, text: str, path: str) -> None:
    try:
        telegram_bot.send_message(chat_id, text, path)
    except Exception:  # noqa: BLE001 - bildirishnoma xatosi asosiy amalni buzmasligi kerak
        logger.exception("Telegram bildirishnomasini yuborib bo'lmadi")


def notify(user, title: str, body: str = "", url: str = "", icon: str = "🔔", kind: str = Notification.Kind.INFO):
    """Foydalanuvchiga bildirishnoma yaratadi.

    Telegram xabari tranzaksiya muvaffaqiyatli yakunlangandan keyin, fonda yuboriladi:
    shunda sekin tarmoq so'rov javobini kechiktirmaydi.
    """
    if not url.startswith("/"):
        url = ""
    notification = Notification.objects.create(user=user, title=title, body=body, url=url, icon=icon, kind=kind)

    chat_id = getattr(user, "telegram_id", None)
    if chat_id and telegram_bot.is_enabled():
        text = f"{icon} {title}" + (f"\n\n{body}" if body else "")

        def send():
            if _run_in_background:
                threading.Thread(target=_deliver_to_telegram, args=(chat_id, text, url), daemon=True).start()
            else:
                _deliver_to_telegram(chat_id, text, url)

        transaction.on_commit(send)
    return notification


def unread_count(user) -> int:
    return Notification.objects.filter(user=user, is_read=False).count()


def mark_all_read(user) -> int:
    return Notification.objects.filter(user=user, is_read=False).update(is_read=True)
