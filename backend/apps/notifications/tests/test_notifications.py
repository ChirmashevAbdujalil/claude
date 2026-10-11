import json
from datetime import timedelta

import pytest
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from apps.discovery import services as discovery
from apps.discovery.models import Challenge, Submission
from apps.notifications import services, telegram_bot
from apps.notifications.models import Notification
from apps.projects import services as projects


@pytest.fixture
def weekly(teacher):
    now = timezone.now()
    return Challenge.objects.create(
        title="Ko'prik loyihasi",
        description="Sxema",
        kind=Challenge.Kind.WEEKLY,
        starts_at=now - timedelta(hours=1),
        ends_at=now + timedelta(days=3),
        created_by=teacher,
    )


@pytest.fixture
def sent(monkeypatch, settings):
    """Telegram'ga yuborilgan xabarlarni yozib boradi (haqiqiy so'rovsiz)."""
    settings.TELEGRAM_BOT_TOKEN = "123:ABC"
    messages = []
    monkeypatch.setattr(services, "_run_in_background", False)
    monkeypatch.setattr(
        telegram_bot, "send_message", lambda chat_id, text, path="": messages.append((chat_id, text, path))
    )
    return messages


def test_review_creates_notification(student, teacher, weekly):
    submission = discovery.submit(weekly, student, answer="Mening yechimim")
    discovery.review(submission, teacher, accept=True, score=80, feedback="Zo'r")
    note = Notification.objects.get(user=student, title__startswith="Yechimingiz qabul qilindi")
    assert "+40 XP" in note.title
    assert note.url == f"/challenges/{weekly.pk}/"


def test_rejection_notifies_with_feedback(student, teacher, weekly):
    submission = discovery.submit(weekly, student, answer="x")
    discovery.review(submission, teacher, accept=False, feedback="Shart to'liq bajarilmagan")
    assert Notification.objects.filter(user=student, body__contains="Shart to'liq bajarilmagan").exists()


def test_badge_and_project_notifications(student, make_user):
    project = projects.create_project(student, title="Dron", description="IoT")
    newcomer = make_user()
    member = projects.request_join(project, newcomer, "Dasturchi")
    assert Notification.objects.filter(user=student, title__contains="qo'shilish so'rovi").exists()
    projects.approve_member(project, student, member.pk)
    titles = list(Notification.objects.filter(user=newcomer).values_list("title", flat=True))
    assert any("jamoasiga qabul qilindingiz" in t for t in titles)
    assert any(t.startswith("Yangi nishon") for t in titles)


def test_telegram_delivery_after_commit(student, sent, django_capture_on_commit_callbacks):
    student.telegram_id = 777
    student.save()
    with django_capture_on_commit_callbacks(execute=True):
        services.notify(student, "Salom", "Matn", url="/arena/", icon="🎉")
    assert sent == [(777, "🎉 Salom\n\nMatn", "/arena/")]


def test_no_telegram_without_telegram_id(student, sent, django_capture_on_commit_callbacks):
    with django_capture_on_commit_callbacks(execute=True):
        services.notify(student, "Salom")
    assert sent == []


def test_external_urls_are_dropped(student):
    assert services.notify(student, "x", url="https://evil.com").url == ""


def test_web_pages_and_mark_read(student):
    services.notify(student, "Birinchi", url="/arena/")
    client = Client()
    client.force_login(student)
    dashboard = client.get(reverse("web:arena")).content.decode()
    assert 'class="dot">1<' in dashboard
    page = client.get(reverse("web:notifications")).content.decode()
    assert "Birinchi" in page and "Yangi" in page
    assert Notification.objects.filter(user=student, is_read=False).count() == 0


def test_notification_go_redirects_and_marks_read(student, make_user):
    note = services.notify(student, "Bor", url="/arena/")
    client = Client()
    client.force_login(student)
    response = client.get(reverse("web:notification-go", args=[note.pk]))
    assert response.url == "/arena/"
    note.refresh_from_db()
    assert note.is_read
    other = Client()
    other.force_login(make_user())
    assert other.get(reverse("web:notification-go", args=[note.pk])).status_code == 404


def test_api_list_and_read_all(api, student):
    services.notify(student, "A")
    services.notify(student, "B")
    client = api(student)
    assert client.get("/api/v1/notifications/?is_read=false").data["count"] == 2
    assert client.post("/api/v1/notifications/read-all/").data == {"updated": 2}


def test_webhook_requires_secret(settings, monkeypatch):
    settings.TELEGRAM_WEBHOOK_SECRET = "s3cret"
    calls = []
    monkeypatch.setattr(telegram_bot, "call", lambda method, payload: calls.append((method, payload)))
    client = Client()
    update = {"message": {"chat": {"id": 5, "type": "private"}, "text": "/start"}}
    url = reverse("telegram-webhook")
    assert client.post(url, json.dumps(update), content_type="application/json").status_code == 403
    bad = client.post(
        url, json.dumps(update), content_type="application/json", headers={"X-Telegram-Bot-Api-Secret-Token": "wrong"}
    )
    assert bad.status_code == 403
    ok = client.post(
        url, json.dumps(update), content_type="application/json", headers={"X-Telegram-Bot-Api-Secret-Token": "s3cret"}
    )
    assert ok.status_code == 200
    assert calls[0][0] == "sendMessage" and "Assalomu alaykum" in calls[0][1]["text"]


def test_open_button_only_for_https(settings):
    settings.SITE_URL = "http://localhost:8000"
    assert telegram_bot.open_button("Ochish") is None
    settings.SITE_URL = "https://talent.adti.uz/"
    button = telegram_bot.open_button("Ochish", "/arena/")
    assert button["inline_keyboard"][0][0]["web_app"]["url"] == "https://talent.adti.uz/arena/"


def test_submission_without_reviewer_does_not_notify(student, teacher):
    now = timezone.now()
    daily = Challenge.objects.create(
        title="Savol",
        description="2+2",
        kind="daily",
        expected_answer="4",
        starts_at=now - timedelta(hours=1),
        ends_at=now + timedelta(hours=5),
        created_by=teacher,
    )
    discovery.submit(daily, student, answer="4")
    assert Submission.objects.get().status == "accepted"
    assert not Notification.objects.filter(title__startswith="Yechimingiz").exists()
