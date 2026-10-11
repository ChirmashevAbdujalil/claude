import json
import time
from datetime import date, timedelta
from types import SimpleNamespace

import pytest
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import User
from apps.accounts.telegram import sign_init_data
from apps.ai import services as ai_services
from apps.ai.models import Conversation
from apps.arena import services as arena
from apps.community.models import Event, Post
from apps.discovery.models import Challenge, Submission
from apps.opportunities.models import Opportunity, Reward
from apps.profiles.models import Achievement, Skill, UserSkill
from apps.projects.models import Project


@pytest.fixture
def web():
    def factory(user=None):
        client = Client()
        if user is not None:
            client.force_login(user)
        return client

    return factory


@pytest.fixture
def content(teacher, student):
    now = timezone.now()
    challenge = Challenge.objects.create(
        title="Ohm qonuni",
        description="12 V, 4 Om. Tok?",
        kind=Challenge.Kind.DAILY,
        expected_answer="3",
        starts_at=now - timedelta(hours=1),
        ends_at=now + timedelta(days=1),
        created_by=teacher,
    )
    weekly = Challenge.objects.create(
        title="Aqlli to'xtash joyi",
        description="Arxitektura",
        kind=Challenge.Kind.WEEKLY,
        starts_at=now - timedelta(hours=1),
        ends_at=now + timedelta(days=7),
        created_by=teacher,
    )
    event = Event.objects.create(
        title="Hakaton",
        description="24 soat",
        location="A-101",
        starts_at=now - timedelta(minutes=10),
        ends_at=now + timedelta(hours=3),
        xp_reward=40,
        created_by=teacher,
    )
    opportunity = Opportunity.objects.create(
        kind=Opportunity.Kind.INTERNSHIP,
        title="Stajirovka",
        description="Python",
        organization="IT Park",
        created_by=teacher,
    )
    project = Project.objects.create(title="Aqlli issiqxona", description="IoT", owner=student)
    project.members.create(user=student, role="Asoschi", status="active")
    post = Post.objects.create(author=student, text="Birinchi robotim!")
    conversation = Conversation.objects.create(user=student)
    student.portfolio_slug = "talaba"
    student.save()
    return SimpleNamespace(
        challenge=challenge,
        weekly=weekly,
        event=event,
        opportunity=opportunity,
        project=project,
        post=post,
        conversation=conversation,
    )


def test_landing_and_login_pages_render(web):
    client = web()
    assert client.get(reverse("web:landing")).status_code == 200
    assert client.get(reverse("web:login")).status_code == 200


def test_landing_redirects_signed_in_user(web, student):
    assert web(student).get(reverse("web:landing")).url == reverse("web:dashboard")


def test_app_pages_require_login(web):
    response = web().get(reverse("web:dashboard"))
    assert response.status_code == 302
    assert response.url.startswith(reverse("web:login"))


def test_login_flow(web, make_user):
    make_user(username="aziz")
    client = web()
    bad = client.post(reverse("web:login"), {"username": "aziz", "password": "wrong"})
    assert "Login yoki parol noto&#x27;g&#x27;ri" in bad.content.decode()
    ok = client.post(reverse("web:login"), {"username": "aziz", "password": "pass12345", "next": "https://evil.com/"})
    assert ok.url == reverse("web:dashboard")


def test_every_student_page_renders(web, student, content):
    client = web(student)
    urls = [
        reverse("web:dashboard"),
        reverse("web:menu"),
        reverse("web:challenges"),
        reverse("web:challenges") + "?tab=mine",
        reverse("web:challenge-detail", args=[content.challenge.pk]),
        reverse("web:arena"),
        reverse("web:arena") + "?tab=league",
        reverse("web:arena") + "?tab=badges",
        reverse("web:arena") + "?tab=history",
        reverse("web:arena") + "?period=week",
        reverse("web:profile"),
        reverse("web:profile-edit"),
        reverse("web:profile-achievement-add"),
        reverse("web:portfolio", args=["talaba"]),
        reverse("web:projects"),
        reverse("web:projects") + "?mine=1&q=issiq",
        reverse("web:project-create"),
        reverse("web:project-detail", args=[content.project.pk]),
        reverse("web:project-edit", args=[content.project.pk]),
        reverse("web:opportunities"),
        reverse("web:opportunity-detail", args=[content.opportunity.pk]),
        reverse("web:shop"),
        reverse("web:feed"),
        reverse("web:post-detail", args=[content.post.pk]),
        reverse("web:events"),
        reverse("web:events") + "?past=1",
        reverse("web:event-detail", args=[content.event.pk]),
        reverse("web:event-checkin"),
        reverse("web:ai"),
        reverse("web:ai-chat", args=[content.conversation.pk]),
    ]
    for url in urls:
        response = client.get(url)
        assert response.status_code == 200, url


def test_staff_pages(web, student, teacher, make_user, content):
    rector = make_user(role=User.Role.RECTOR)
    staff_urls = [reverse("web:review"), reverse("web:challenge-create"), reverse("web:event-create")]
    for url in staff_urls:
        assert web(student).get(url).status_code == 403, url
        assert web(teacher).get(url).status_code == 200, url
    assert web(teacher).get(reverse("web:review") + "?tab=achievements").status_code == 200
    assert web(teacher).get(reverse("web:event-detail", args=[content.event.pk])).status_code == 200
    assert web(teacher).get(reverse("web:insights")).status_code == 403
    assert web(rector).get(reverse("web:insights")).status_code == 200


def test_submit_daily_challenge_and_celebrate(web, student, content):
    client = web(student)
    url = reverse("web:challenge-detail", args=[content.challenge.pk])
    response = client.post(url, {"answer": "3"}, follow=True)
    assert "To'g'ri javob!" in response.content.decode()
    student.refresh_from_db()
    assert student.xp == 30  # 10 XP + "Birinchi qadam" nishoni


def test_teacher_reviews_submission_on_web(web, student, teacher, content):
    web(student).post(reverse("web:challenge-detail", args=[content.weekly.pk]), {"answer": "Mening sxemam"})
    submission = Submission.objects.get(challenge=content.weekly)
    response = web(teacher).post(
        reverse("web:review-submission", args=[submission.pk]),
        {"decision": "accept", "score": "60", "feedback": "Yaxshi"},
    )
    assert response.status_code == 302
    submission.refresh_from_db()
    assert submission.status == Submission.Status.ACCEPTED
    assert submission.xp_awarded == 30


def test_teacher_approves_achievement_on_web(web, student, teacher):
    achievement = Achievement.objects.create(
        user=student, kind="certificate", title="AWS", achieved_on=date(2026, 5, 1), proof_url="https://x.uz"
    )
    web(teacher).post(reverse("web:review-achievement", args=[achievement.pk]), {"decision": "approve", "xp": "120"})
    achievement.refresh_from_db()
    assert achievement.status == Achievement.Status.APPROVED and achievement.xp_awarded == 120


def test_profile_skill_and_achievement_forms(web, student):
    client = web(student)
    python = Skill.objects.get(name="Python")
    client.post(reverse("web:profile-skill-add"), {"skill": python.pk, "level": "4"})
    assert UserSkill.objects.filter(user=student, skill=python, level=4).exists()
    response = client.post(
        reverse("web:profile-achievement-add"),
        {"kind": "olympiad", "title": "Olimpiada", "achieved_on": "2026-04-01", "proof_url": "https://x.uz"},
    )
    assert response.status_code == 302
    assert Achievement.objects.filter(user=student, status="pending").count() == 1


def test_teacher_endorses_and_flags_from_portfolio(web, student, teacher):
    student.portfolio_slug = "aziz"
    student.save()
    user_skill = UserSkill.objects.create(user=student, skill=Skill.objects.get(name="Python"))
    client = web(teacher)
    page = client.get(reverse("web:portfolio", args=["aziz"])).content.decode()
    assert "Iqtidor belgisi" in page
    client.post(reverse("web:endorse-skill", args=[user_skill.pk]))
    assert user_skill.endorsements.count() == 1
    client.post(reverse("web:talent-flag", args=[student.pk]), {"area": "programming", "note": "Ajoyib algoritm"})
    assert student.talent_flags.count() == 1


def test_private_portfolio_hidden_from_strangers(web, student, make_user):
    student.portfolio_slug = "yopiq"
    student.is_public = False
    student.save()
    assert web().get(reverse("web:portfolio", args=["yopiq"])).status_code == 404
    assert web(make_user()).get(reverse("web:portfolio", args=["yopiq"])).status_code == 404
    assert web(student).get(reverse("web:portfolio", args=["yopiq"])).status_code == 200


def test_project_create_join_and_approve(web, student, make_user):
    client = web(student)
    response = client.post(
        reverse("web:project-create"),
        {"title": "Dron", "description": "Qishloq xo'jaligi uchun", "is_recruiting": "on"},
    )
    project = Project.objects.get(title="Dron")
    assert response.url == reverse("web:project-detail", args=[project.pk])
    newcomer = make_user()
    web(newcomer).post(reverse("web:project-join", args=[project.pk]), {"role": "Dasturchi"})
    member = project.members.get(user=newcomer)
    client.post(reverse("web:project-approve", args=[project.pk, member.pk]))
    member.refresh_from_db()
    assert member.status == "active"
    assert web(newcomer).get(reverse("web:project-edit", args=[project.pk])).status_code == 403


def test_shop_redeem(web, student):
    reward = Reward.objects.get(name="Oshxona taloni")
    client = web(student)
    page = client.post(reverse("web:shop-redeem", args=[reward.pk]), follow=True).content.decode()
    assert "Tangalar yetarli emas" in page
    arena.award(student, arena.Reason.MANUAL, 300)
    client.post(reverse("web:shop-redeem", args=[reward.pk]))
    student.refresh_from_db()
    assert student.coins == 10


def test_apply_to_opportunity(web, student, content):
    url = reverse("web:opportunity-detail", args=[content.opportunity.pk])
    web(student).post(url, {"motivation": "Men Python bo'yicha tajriba orttirmoqchiman, juda qiziqaman."})
    assert content.opportunity.applications.filter(user=student).exists()


def test_like_via_fetch_returns_json(web, make_user, content):
    response = web(make_user()).post(
        reverse("web:post-like", args=[content.post.pk]), headers={"X-Requested-With": "fetch"}
    )
    assert response.json() == {"liked": True, "like_count": 1}


def test_like_redirect_ignores_external_next(web, make_user, content):
    response = web(make_user()).post(reverse("web:post-like", args=[content.post.pk]), {"next": "https://evil.com"})
    assert response.url == reverse("web:feed")


def test_feed_post_and_comment(web, student, content):
    client = web(student)
    client.post(reverse("web:feed"), {"text": "Yangi yutuq!"})
    assert Post.objects.filter(text="Yangi yutuq!").exists()
    client.post(reverse("web:post-detail", args=[content.post.pk]), {"text": "Zo'r!"})
    assert content.post.comments.count() == 1


def test_event_qr_checkin_flow(web, student, teacher, content):
    detail = web(teacher).get(reverse("web:event-detail", args=[content.event.pk])).content.decode()
    assert content.event.checkin_code in detail
    client = web(student)
    page = client.get(reverse("web:event-checkin") + f"?code={content.event.checkin_code}").content.decode()
    assert "Men shu yerdaman" in page
    client.post(reverse("web:event-checkin"), {"code": content.event.checkin_code})
    student.refresh_from_db()
    assert student.xp == 40
    # Talaba QR kodni ko'rmaydi
    assert (
        content.event.checkin_code
        not in client.get(reverse("web:event-detail", args=[content.event.pk])).content.decode()
    )


def test_ai_chat_on_web(web, student, monkeypatch):
    calls = []

    def create(**kwargs):
        calls.append(kwargs)
        return SimpleNamespace(
            content=[SimpleNamespace(type="text", text="Keling, reja tuzamiz!")],
            stop_reason="end_turn",
            usage=SimpleNamespace(input_tokens=1, output_tokens=1),
        )

    fake = SimpleNamespace(beta=SimpleNamespace(messages=SimpleNamespace(create=create)))
    monkeypatch.setattr(ai_services, "get_client", lambda: fake)
    client = web(student)
    response = client.post(reverse("web:ai-start"), {"mode": "mentor", "text": "Python o'rganmoqchiman"})
    conversation = Conversation.objects.get(user=student)
    assert response.url == reverse("web:ai-chat", args=[conversation.pk])
    page = client.get(response.url).content.decode()
    assert "Keling, reja tuzamiz!" in page
    assert len(calls) == 1


def test_other_users_conversation_is_hidden(web, make_user, content):
    assert web(make_user()).get(reverse("web:ai-chat", args=[content.conversation.pk])).status_code == 404


def test_telegram_web_login(web, settings):
    settings.TELEGRAM_BOT_TOKEN = "123:ABC"
    fields = {"auth_date": str(int(time.time())), "user": json.dumps({"id": 555, "first_name": "Laylo"})}
    client = web()
    response = client.post(reverse("web:telegram-login"), {"init_data": sign_init_data(fields, "123:ABC")})
    assert response.json() == {"created": True}
    # Yangi talaba avval boshlang'ich sozlashga yo'naltiriladi
    assert client.get(reverse("web:dashboard")).url == reverse("web:welcome")
    assert web().post(reverse("web:telegram-login"), {"init_data": "hash=bad"}).status_code == 401


def test_404_page(web):
    response = web().get("/mavjud-emas/")
    assert response.status_code == 404


def test_ai_without_api_key_shows_message(web, student, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "")
    monkeypatch.delenv("ANTHROPIC_AUTH_TOKEN", raising=False)
    client = web(student)
    assert "AI Mentor hali ulanmagan" in client.get(reverse("web:ai")).content.decode()
    response = client.post(reverse("web:ai-start"), {"mode": "mentor", "text": "Salom"}, follow=True)
    assert response.status_code == 200
    assert ai_services.NOT_CONFIGURED in response.content.decode().replace("&#x27;", "'")
