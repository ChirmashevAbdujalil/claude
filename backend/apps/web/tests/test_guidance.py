import json
from datetime import timedelta
from types import SimpleNamespace

import pytest
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import User
from apps.ai import services as ai_services
from apps.arena import services as arena
from apps.discovery.models import Challenge, Submission
from apps.profiles.models import Skill, UserSkill
from apps.web.guidance import next_steps, profile_checklist
from apps.web.templatetags.web_tags import stepper


@pytest.fixture
def web():
    def factory(user=None):
        client = Client()
        if user is not None:
            client.force_login(user)
        return client

    return factory


@pytest.fixture
def daily(teacher):
    now = timezone.now()
    return Challenge.objects.create(
        title="Kunlik savol",
        description="2+2?",
        kind=Challenge.Kind.DAILY,
        expected_answer="4",
        starts_at=now - timedelta(hours=1),
        ends_at=now + timedelta(hours=10),
        created_by=teacher,
    )


# ---------- Ro'yxatdan o'tish ----------


def test_register_creates_student_and_logs_in(web, faculty):
    client = web()
    response = client.post(
        reverse("web:register"),
        {
            "first_name": "Laylo",
            "last_name": "Karimova",
            "username": "laylo",
            "password1": "Kuchli-parol-2026",
            "password2": "Kuchli-parol-2026",
            "role": "admin",
        },
    )
    assert response.url == reverse("web:welcome")
    user = User.objects.get(username="laylo")
    assert user.role == User.Role.STUDENT
    assert user.onboarded_at is None
    assert client.get(reverse("web:dashboard")).url == reverse("web:welcome")


def test_register_validates_passwords(web):
    response = web().post(
        reverse("web:register"),
        {"first_name": "A", "last_name": "B", "username": "ab", "password1": "123", "password2": "456"},
    )
    assert response.status_code == 200
    assert not User.objects.filter(username="ab").exists()


def test_registration_can_be_closed(web, settings):
    settings.REGISTRATION_OPEN = False
    assert web().get(reverse("web:register")).status_code == 404
    assert "Ro&#x27;yxatdan o&#x27;ting" not in web().get(reverse("web:login")).content.decode()


# ---------- Onboarding ----------


def test_onboarding_flow(web, faculty, daily):
    user = User.objects.create_user(username="yangi", password="x", first_name="Aziz", last_name="Karimov")
    client = web(user)
    assert client.get(reverse("web:welcome")).status_code == 200

    response = client.post(reverse("web:welcome"), {"faculty": faculty.pk, "course": 1})
    assert response.url.endswith("?step=2")
    user.refresh_from_db()
    assert user.faculty == faculty and user.course == 1 and user.portfolio_slug == "aziz-karimov"

    skills = Skill.objects.filter(name__in=["Python", "Robototexnika", "Ingliz tili"])
    client.post(reverse("web:welcome") + "?step=2", {"skills": [s.pk for s in skills]})
    assert UserSkill.objects.filter(user=user).count() == 3

    page = client.get(reverse("web:welcome") + "?step=3").content.decode()
    assert "Hammasi tayyor" in page and "Birinchi challenge" in page
    user.refresh_from_db()
    assert user.onboarded_at is not None
    assert user.badges.filter(badge__code="welcome").exists()
    assert client.get(reverse("web:dashboard")).status_code == 200


def test_onboarding_requires_faculty(web):
    user = User.objects.create_user(username="yangi2", password="x")
    response = web(user).post(reverse("web:welcome"), {"faculty": "", "course": ""})
    assert response.status_code == 200
    user.refresh_from_db()
    assert user.faculty is None


def test_onboarding_skip(web):
    user = User.objects.create_user(username="shoshilgan", password="x")
    web(user).post(reverse("web:welcome-skip"))
    user.refresh_from_db()
    assert user.onboarded_at is not None


def test_teacher_not_sent_to_onboarding(web):
    teacher = User.objects.create_user(username="ustoz", password="x", role=User.Role.TEACHER)
    assert web(teacher).get(reverse("web:dashboard")).status_code == 200


# ---------- Keyingi qadam ----------


def test_next_steps_for_new_student(make_user, daily):
    student = make_user()
    steps = next_steps(student)
    assert steps[0].title == "Ko'nikmalaringizni qo'shing"
    assert any(step.title == "Bugungi savolni yeching" and step.xp == 10 for step in steps)


def test_streak_at_risk_comes_first_without_duplicates(make_user, daily):
    student = make_user()
    UserSkill.objects.create(user=student, skill=Skill.objects.get(name="Python"))
    today = timezone.localdate()
    arena.touch_streak(student, today - timedelta(days=2))
    arena.touch_streak(student, today - timedelta(days=1))
    steps = next_steps(student, limit=5)
    assert steps[0].title.startswith("2 kunlik streakni")
    assert len({step.url for step in steps}) == len(steps)


def test_dashboard_shows_next_step_and_checklist(web, make_user, daily):
    page = web(make_user()).get(reverse("web:dashboard")).content.decode()
    assert "Keyingi qadamingiz" in page
    assert "Profil to'liqligi" in page


def test_profile_checklist(make_user):
    student = make_user(bio="Robototexnika", portfolio_slug="x")
    checklist = profile_checklist(student)
    assert checklist["done"] == 3 and checklist["total"] == 6 and checklist["percent"] == 50


# ---------- Ball qoidalari va stepper ----------


def test_how_it_works_is_public_and_uses_constants(web):
    page = web().get(reverse("web:how-it-works")).content.decode()
    assert "Qanday ball olaman?" in page
    assert "300 XP" in page and "Har 10 XP = 2 tanga" in page


def test_stepper_states():
    pending = stepper("submission", "pending")["steps"]
    assert [s["state"] for s in pending] == ["done", "current", "todo"]
    rejected = stepper("achievement", "rejected")["steps"]
    assert rejected[-1] == {"label": "Rad etildi", "state": "failed"}
    shortlisted = stepper("application", "shortlisted")["steps"]
    assert [s["state"] for s in shortlisted] == ["done", "done", "done", "current"]


def test_level_card_shows_remaining_xp(web, make_user):
    student = make_user()
    UserSkill.objects.create(user=student, skill=Skill.objects.get(name="Python"))
    arena.award(student, arena.Reason.MANUAL, 120)
    page = web(student).get(reverse("web:dashboard")).content.decode()
    assert "darajasigacha 380 XP" in page


# ---------- AI tekshiruv yordamchisi ----------


class FakeReviewClient:
    def __init__(self, payload=None, stop_reason="end_turn"):
        self.payload = payload
        self.stop_reason = stop_reason
        self.calls = []
        self.beta = SimpleNamespace(messages=SimpleNamespace(create=self.create))

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(
            content=[SimpleNamespace(type="text", text=json.dumps(self.payload or {}))],
            stop_reason=self.stop_reason,
            usage=SimpleNamespace(input_tokens=1, output_tokens=1),
        )


@pytest.fixture
def weekly_submission(teacher, make_user):
    now = timezone.now()
    challenge = Challenge.objects.create(
        title="Ko'prik",
        description="Ko'prik sxemasini taklif qiling",
        kind=Challenge.Kind.WEEKLY,
        starts_at=now - timedelta(hours=1),
        ends_at=now + timedelta(days=3),
        created_by=teacher,
    )
    student = make_user(first_name="Maxfiy", last_name="Ism")
    return Submission.objects.create(challenge=challenge, user=student, answer="Arkali ko'prik, po'lat")


def test_ai_suggestion_prefills_review_form(web, teacher, weekly_submission, monkeypatch):
    fake = FakeReviewClient(
        {
            "score": 140,
            "feedback": "Yaxshi g'oya, hisob-kitob qo'shing.",
            "strengths": ["Aniq sxema"],
            "improvements": ["Yuklama hisobi"],
        }
    )
    monkeypatch.setattr(ai_services, "get_client", lambda: fake)
    monkeypatch.setattr(ai_services, "is_configured", lambda: True)
    client = web(teacher)
    client.post(reverse("web:review-submission-ai", args=[weekly_submission.pk]))
    weekly_submission.refresh_from_db()
    assert weekly_submission.ai_suggestion["score"] == 100  # chegaraga keltiriladi

    call = fake.calls[0]
    assert call["output_config"]["format"]["type"] == "json_schema"
    assert "Maxfiy" not in call["messages"][0]["content"]

    page = client.get(reverse("web:review")).content.decode()
    assert "AI taklifi: 100/100" in page
    assert 'value="Yaxshi g&#x27;oya, hisob-kitob qo&#x27;shing."' in page
    assert weekly_submission.status == Submission.Status.PENDING


def test_ai_refusal_shows_error(web, teacher, weekly_submission, monkeypatch):
    monkeypatch.setattr(ai_services, "get_client", lambda: FakeReviewClient(stop_reason="refusal"))
    response = web(teacher).post(reverse("web:review-submission-ai", args=[weekly_submission.pk]), follow=True)
    assert "qo&#x27;lda tekshiring" in response.content.decode()
    weekly_submission.refresh_from_db()
    assert weekly_submission.ai_suggestion is None


def test_ai_review_requires_reviewer(web, student, weekly_submission):
    assert web(student).post(reverse("web:review-submission-ai", args=[weekly_submission.pk])).status_code == 403
