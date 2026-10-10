import json
import time

import pytest

from apps.accounts.models import User
from apps.accounts.telegram import TelegramAuthError, sign_init_data, verify_init_data

BOT_TOKEN = "123456:TEST-TOKEN"


def make_init_data(user_id=777, auth_date=None, token=BOT_TOKEN):
    fields = {
        "auth_date": str(auth_date or int(time.time())),
        "query_id": "AAH",
        "user": json.dumps({"id": user_id, "first_name": "Aziz", "last_name": "Karimov"}),
    }
    return sign_init_data(fields, token)


def test_verify_valid_init_data():
    user = verify_init_data(make_init_data(), BOT_TOKEN, max_age=60)
    assert user["id"] == 777


def test_verify_rejects_wrong_signature():
    with pytest.raises(TelegramAuthError):
        verify_init_data(make_init_data(token="other:token"), BOT_TOKEN, max_age=60)


def test_verify_rejects_tampered_data():
    data = make_init_data().replace("Aziz", "Hacker")
    with pytest.raises(TelegramAuthError):
        verify_init_data(data, BOT_TOKEN, max_age=60)


def test_verify_rejects_expired():
    old = int(time.time()) - 3600
    with pytest.raises(TelegramAuthError, match="muddati"):
        verify_init_data(make_init_data(auth_date=old), BOT_TOKEN, max_age=60)


def test_telegram_login_creates_user_once(api, settings):
    settings.TELEGRAM_BOT_TOKEN = BOT_TOKEN
    client = api()
    first = client.post("/api/v1/auth/telegram/", {"init_data": make_init_data(user_id=42)}, format="json")
    assert first.status_code == 200
    assert first.data["created"] is True
    assert first.data["access"]

    second = client.post("/api/v1/auth/telegram/", {"init_data": make_init_data(user_id=42)}, format="json")
    assert second.data["created"] is False
    user = User.objects.get(telegram_id=42)
    assert user.first_name == "Aziz"
    assert not user.has_usable_password()


def test_telegram_login_bad_signature(api, settings):
    settings.TELEGRAM_BOT_TOKEN = BOT_TOKEN
    response = api().post("/api/v1/auth/telegram/", {"init_data": "user=1&hash=abc"}, format="json")
    assert response.status_code == 401


def test_me_update_profile(api, student):
    client = api(student)
    response = client.patch("/api/v1/me/", {"bio": "Robototexnika ishqibozi", "course": 3}, format="json")
    assert response.status_code == 200
    assert response.data["course"] == 3
    assert response.data["level"]["name"] == "Yangi boshlovchi"


def test_me_cannot_change_role_or_xp(api, student):
    client = api(student)
    client.patch("/api/v1/me/", {"role": "admin", "xp": 99999, "course": 9}, format="json")
    student.refresh_from_db()
    assert student.role == User.Role.STUDENT
    assert student.xp == 0


def test_me_requires_auth(api):
    assert api().get("/api/v1/me/").status_code == 401
