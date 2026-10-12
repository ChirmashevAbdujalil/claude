"""Telegram Bot API bilan ishlash: xabar yuborish va /start buyrug'iga javob.

Tashqi kutubxonasiz, standart urllib orqali. Xatolar platformani to'xtatmaydi, faqat logga yoziladi.
"""

import json
import logging
import urllib.error
import urllib.request

from django.conf import settings

logger = logging.getLogger(__name__)

API_URL = "https://api.telegram.org/bot{token}/{method}"
TIMEOUT = 8


def is_enabled() -> bool:
    return bool(settings.TELEGRAM_BOT_TOKEN)


def call(method: str, payload: dict) -> dict | None:
    """Bot API metodini chaqiradi. Muvaffaqiyatsiz bo'lsa `None` qaytaradi."""
    if not is_enabled():
        return None
    request = urllib.request.Request(
        API_URL.format(token=settings.TELEGRAM_BOT_TOKEN, method=method),
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
            return json.loads(response.read())
    except (urllib.error.URLError, TimeoutError, ValueError) as exc:
        logger.warning("Telegram %s xatosi: %s", method, exc)
        return None


def open_button(text: str, path: str = "/app/") -> dict | None:
    """Saytni Telegram ichida (Mini App) ochadigan tugma. SITE_URL https bo'lishi shart."""
    site = settings.SITE_URL.rstrip("/")
    if not site.startswith("https://"):
        return None
    return {"inline_keyboard": [[{"text": text, "web_app": {"url": f"{site}{path}"}}]]}


def send_message(chat_id: int, text: str, path: str = "") -> bool:
    payload = {"chat_id": chat_id, "text": text, "disable_web_page_preview": True}
    markup = open_button("Platformada ochish", path or "/app/")
    if markup:
        payload["reply_markup"] = markup
    result = call("sendMessage", payload)
    return bool(result and result.get("ok"))


WELCOME_TEXT = (
    "Assalomu alaykum! 👋\n\n"
    "Bu ANDTI Talent Hub: iqtidoringizni kashf qiluvchi platforma.\n\n"
    "🎯 Challenge'lar yeching va XP to'plang\n"
    "🚀 Loyihalar quring va jamoa toping\n"
    "🤖 AI Mentor bilan o'z yo'lingizni tuzing\n"
    "🎁 Tangalarni real sovg'alarga almashtiring\n\n"
    "Boshlash uchun pastdagi tugmani bosing."
)


def handle_update(update: dict) -> None:
    """Botga kelgan xabarga javob beradi (webhook orqali)."""
    message = update.get("message") or {}
    chat = message.get("chat") or {}
    text = (message.get("text") or "").strip()
    if chat.get("type") != "private" or not chat.get("id"):
        return
    if text.startswith("/start") or text.startswith("/help"):
        reply = WELCOME_TEXT
    else:
        reply = "Platformani ochish uchun pastdagi tugmani bosing 👇"
    payload = {"chat_id": chat["id"], "text": reply}
    markup = open_button("🚀 Platformani ochish")
    if markup:
        payload["reply_markup"] = markup
    call("sendMessage", payload)
