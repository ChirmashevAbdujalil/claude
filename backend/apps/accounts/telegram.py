"""Telegram Mini App `initData` imzosini tekshirish.

https://core.telegram.org/bots/webapps#validating-data-received-via-the-mini-app
"""

import hashlib
import hmac
import json
import time
from urllib.parse import parse_qsl


class TelegramAuthError(Exception):
    pass


def verify_init_data(init_data: str, bot_token: str, max_age: int, now: float | None = None) -> dict:
    """Imzo to'g'ri bo'lsa Telegram foydalanuvchi ma'lumotlarini qaytaradi."""
    if not bot_token:
        raise TelegramAuthError("Telegram bot sozlanmagan")

    fields = dict(parse_qsl(init_data, keep_blank_values=True, strict_parsing=False))
    received_hash = fields.pop("hash", None)
    if not received_hash:
        raise TelegramAuthError("Imzo topilmadi")

    data_check_string = "\n".join(f"{key}={fields[key]}" for key in sorted(fields))
    secret_key = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    expected_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected_hash, received_hash):
        raise TelegramAuthError("Imzo noto'g'ri")

    try:
        auth_date = int(fields.get("auth_date", "0"))
    except ValueError as exc:
        raise TelegramAuthError("auth_date noto'g'ri") from exc
    current = now if now is not None else time.time()
    if current - auth_date > max_age:
        raise TelegramAuthError("Sessiya muddati o'tgan, ilovani qayta oching")

    try:
        user = json.loads(fields.get("user", ""))
    except json.JSONDecodeError as exc:
        raise TelegramAuthError("Foydalanuvchi ma'lumotlari noto'g'ri") from exc
    if not isinstance(user, dict) or "id" not in user:
        raise TelegramAuthError("Foydalanuvchi ma'lumotlari topilmadi")
    return user


def sign_init_data(fields: dict[str, str], bot_token: str) -> str:
    """Testlar va lokal ishlab chiqish uchun imzolangan initData yasaydi."""
    from urllib.parse import urlencode

    data_check_string = "\n".join(f"{key}={fields[key]}" for key in sorted(fields))
    secret_key = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    signature = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()
    return urlencode({**fields, "hash": signature})


def get_or_create_telegram_user(tg_user: dict):
    """Telegram foydalanuvchisini joriy OTMda topadi yoki yaratadi.

    Bitta Telegram hisobi faqat bitta OTMga ulanadi: boshqa OTMda bo'lsa, xato qaytaradi.
    """
    from django.contrib.auth import get_user_model
    from django.db import transaction

    from apps.tenants.context import current, unscoped

    User = get_user_model()
    with unscoped():
        existing = User.objects.filter(telegram_id=tg_user["id"]).first()
    institution = current()
    if existing is not None:
        if institution is not None and existing.institution_id != institution.pk:
            raise TelegramAuthError("Bu Telegram hisobi boshqa OTMga ulangan")
        return existing, False
    with transaction.atomic():
        user = User(
            telegram_id=tg_user["id"],
            username=f"tg{tg_user['id']}",
            first_name=tg_user.get("first_name", "")[:150],
            last_name=tg_user.get("last_name", "")[:150],
        )
        user.set_unusable_password()
        user.save()
    return user, True
