import json
from datetime import date
from types import SimpleNamespace

import pytest

from apps.ai import services as ai_services
from apps.arena.models import Badge, UserBadge
from apps.profiles import resume as resume_lib
from apps.profiles.models import Achievement, Endorsement, Skill, UserSkill
from apps.projects import services as project_services


class FakeClient:
    def __init__(self, payload):
        self.calls = []
        self.payload = payload
        self.beta = SimpleNamespace(messages=SimpleNamespace(create=self.create))

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(
            content=[SimpleNamespace(type="text", text=json.dumps(self.payload))],
            stop_reason="end_turn",
            usage=SimpleNamespace(input_tokens=10, output_tokens=10),
        )


@pytest.fixture
def rich_student(make_user, teacher):
    user = make_user(first_name="Aziza", last_name="Rahimova", email="aziza@example.com", portfolio_slug="aziza")
    python = UserSkill.objects.create(user=user, skill=Skill.objects.get(name="Python"), level=4)
    Endorsement.objects.create(user_skill=python, endorsed_by=teacher)
    Achievement.objects.create(
        user=user,
        kind=Achievement.Kind.HACKATHON,
        title="Andijon Hackathon g'olibi",
        achieved_on=date(2026, 5, 1),
        status=Achievement.Status.APPROVED,
    )
    Achievement.objects.create(user=user, kind="other", title="Tekshirilmagan yutuq", achieved_on=date(2026, 6, 1))
    project_services.create_project(user, title="Aqlli issiqxona", description="IoT datchiklar bilan issiqxona")
    UserBadge.objects.create(user=user, badge=Badge.objects.get(code="first-challenge"))
    return user


def test_collect_uses_only_verified_data(rich_student):
    data = resume_lib.collect(rich_student, "uz")
    assert data.name == "Aziza Rahimova"
    assert data.skills == [{"name": "Python", "level": 4, "endorsed": True}]
    assert [a["title"] for a in data.achievements] == ["Andijon Hackathon g'olibi"]
    assert data.projects[0]["title"] == "Aqlli issiqxona" and data.projects[0]["role"] == "Asoschi"
    assert data.badges == ["Birinchi qadam"]
    assert "Python" in data.summary  # avtomatik xulosa
    assert ("Email", "aziza@example.com") in data.contacts


def test_public_resume_hides_private_contacts(rich_student):
    resume = resume_lib.get_resume(rich_student)
    resume.phone = "+998901234567"
    resume.save()
    hidden = resume_lib.collect(rich_student, "uz", public=True)
    assert all(label not in ("Email", "Tel") for label, _ in hidden.contacts)
    resume.show_contacts_public = True
    resume.save()
    shown = resume_lib.collect(rich_student, "uz", public=True)
    assert ("Tel", "+998901234567") in shown.contacts


def test_english_labels(rich_student):
    data = resume_lib.collect(rich_student, "en")
    assert data.achievements[0]["kind"] == "Hackathon"
    assert data.projects[0]["stage"] == "Idea"
    assert "Andijan State Technical Institute" in data.summary


def test_pdf_download(client, rich_student):
    client.force_login(rich_student)
    response = client.get("/profile/resume.pdf?lang=en")
    assert response.status_code == 200
    assert response["Content-Type"] == "application/pdf"
    assert 'filename="cv-' in response["Content-Disposition"]
    assert response.content.startswith(b"%PDF")


def test_pdf_handles_cyrillic_and_long_content(client, make_user):
    user = make_user(first_name="Азиз", last_name="Каримов")
    for i in range(12):
        Achievement.objects.create(
            user=user,
            kind="certificate",
            title=f"Sertifikat {i} «Ma'lumotlar tahlili»",
            description="Uzun tavsif " * 40,
            achieved_on=date(2026, 1, 1),
            status=Achievement.Status.APPROVED,
        )
    client.force_login(user)
    response = client.get("/profile/resume.pdf")
    assert response.content.startswith(b"%PDF")


def test_resume_page_saves_text_and_email(client, rich_student):
    client.force_login(rich_student)
    assert client.get("/profile/resume/").status_code == 200
    response = client.post(
        "/profile/resume/",
        {"headline": "IoT muhandisi", "summary": "Qisqa matn", "email": "new@example.com", "phone": ""},
    )
    assert response.status_code == 302
    rich_student.refresh_from_db()
    assert rich_student.email == "new@example.com"
    assert rich_student.resume.headline == "IoT muhandisi"
    assert "IoT muhandisi" in client.get("/profile/resume/").content.decode()


def test_public_resume_requires_public_profile(client, rich_student):
    assert client.get("/u/aziza/resume.pdf").status_code == 200
    rich_student.is_public = False
    rich_student.save()
    assert client.get("/u/aziza/resume.pdf").status_code == 404


def test_ai_writes_resume_without_sending_name(rich_student, monkeypatch):
    client = FakeClient({"headline": "IoT talaba-muhandisi", "summary": "Python va IoT bo'yicha kuchli talaba."})
    monkeypatch.setattr(ai_services, "get_client", lambda: client)
    result = ai_services.write_resume(rich_student, "uz")
    assert result["summary"].startswith("Python")
    resume = rich_student.resume
    resume.refresh_from_db()
    assert resume.summary.startswith("Python") and resume.headline == "IoT talaba-muhandisi"
    sent = client.calls[0]["messages"][0]["content"]
    assert "Aziza" not in sent and "Rahimova" not in sent and "aziza@example.com" not in sent
    assert "Andijon Hackathon g'olibi" in sent
    assert client.calls[0]["output_config"]["format"]["type"] == "json_schema"


def test_ai_keeps_custom_headline_and_limits_daily_use(rich_student, monkeypatch, settings):
    settings.RESUME_AI_DAILY_LIMIT = 1
    resume = resume_lib.get_resume(rich_student)
    resume.headline_en = "My own headline"
    resume.save()
    client = FakeClient({"headline": "AI headline", "summary": "Strong engineering student."})
    monkeypatch.setattr(ai_services, "get_client", lambda: client)
    ai_services.write_resume(rich_student, "en")
    resume.refresh_from_db()
    assert resume.headline_en == "My own headline"
    assert resume.summary_en == "Strong engineering student."
    with pytest.raises(ai_services.AiLimitExceeded):
        ai_services.write_resume(rich_student, "en")


def test_ai_button_without_key_shows_message(client, rich_student, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_AUTH_TOKEN", raising=False)
    client.force_login(rich_student)
    response = client.post("/profile/resume/ai/", {"lang": "uz"}, follow=True)
    assert "AI Mentor hali sozlanmagan" in response.content.decode()
