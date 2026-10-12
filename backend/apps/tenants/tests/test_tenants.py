from datetime import timedelta

import pytest
from django.core.management import call_command
from django.utils import timezone

from apps.accounts.models import Faculty, User
from apps.accounts.telegram import TelegramAuthError, get_or_create_telegram_user
from apps.ai import services as ai_services
from apps.ai.models import Conversation
from apps.discovery.models import Challenge
from apps.opportunities.models import Reward
from apps.tenants import plans, services
from apps.tenants.context import activate, default_institution, unscoped
from apps.tenants.middleware import UnknownInstitution, resolve
from apps.tenants.models import Institution, InstitutionRequest

TATU = "tatu.localhost"
NOW = timezone.now()
OPEN = {"xp_reward": 10, "starts_at": NOW - timedelta(days=1), "ends_at": NOW + timedelta(days=7), "is_published": True}


@pytest.fixture
def tatu(db):
    institution, _, _ = services.create_institution(
        name="Toshkent axborot texnologiyalari universiteti", short_name="TATU", slug="tatu", plan="standart"
    )
    return institution


@pytest.fixture
def tatu_user(tatu):
    def factory(username="tatu_student", role=User.Role.STUDENT, **kwargs):
        with activate(tatu):
            faculty = Faculty.objects.get_or_create(name="Dasturiy injiniring", short_name="DI")[0]
            return User.objects.create_user(
                username=username, password="pass12345", role=role, faculty=faculty, **kwargs
            )

    return factory


def host(client, name=TATU):
    client.defaults["HTTP_HOST"] = name
    return client


# ---------------------------------------------------------------- manzil bo'yicha aniqlash


def test_resolve_by_host(tatu, settings):
    assert resolve("localhost:8000").is_default
    assert resolve("tatu.localhost:8000") == tatu
    with pytest.raises(UnknownInstitution):
        resolve("nomalum.localhost")
    settings.SAAS_BASE_DOMAIN = "talenthub.uz"
    assert resolve("talenthub.uz") is None
    assert resolve("tatu.talenthub.uz") == tatu
    tatu.domain = "talent.tuit.uz"
    tatu.save()
    assert resolve("talent.tuit.uz") == tatu


def test_existing_data_belongs_to_default_institution(student, faculty):
    default = default_institution()
    assert student.institution == default and faculty.institution == default
    assert default.plan == "premium"


# ---------------------------------------------------------------- ma'lumotlar ajratilganligi


def test_users_and_content_are_isolated(client, student, teacher, tatu, tatu_user):
    other = tatu_user()
    Challenge.objects.create(title="ANDTI vazifasi", description="x", created_by=teacher, **OPEN)
    with activate(tatu):
        Challenge.objects.create(
            title="TATU vazifasi",
            description="x",
            created_by=tatu_user("tatu_teacher", User.Role.TEACHER),
            **OPEN,
        )
        assert set(User.objects.values_list("username", flat=True)) == {"tatu_student", "tatu_teacher", "tatu_admin"}
        assert list(Challenge.objects.values_list("title", flat=True)) == ["TATU vazifasi"]
    with activate(default_institution()):
        assert not User.objects.filter(pk=other.pk).exists()
        assert "TATU vazifasi" not in Challenge.objects.values_list("title", flat=True)

    host(client).force_login(other)
    body = client.get("/challenges/").content.decode()
    assert "TATU vazifasi" in body and "ANDTI vazifasi" not in body


def test_session_from_other_institution_is_not_accepted(client, student, tatu):
    host(client).force_login(student)  # ANDTI foydalanuvchisi TATU manzilida
    response = client.get("/app/")
    assert response.status_code == 302 and "/login/" in response["Location"]


def test_login_works_only_on_own_institution(client, tatu, tatu_user):
    tatu_user()
    response = host(client, "localhost").post("/login/", {"username": "tatu_student", "password": "pass12345"})
    assert response.status_code == 200  # ANDTI manzilida bunday foydalanuvchi yo'q
    response = host(client).post("/login/", {"username": "tatu_student", "password": "pass12345"})
    assert response.status_code == 302


def test_portfolio_of_other_institution_is_hidden(client, make_user, tatu):
    make_user(portfolio_slug="aziza")
    assert host(client, "localhost").get("/u/aziza/").status_code == 200
    assert host(client).get("/u/aziza/").status_code == 404


def test_reverse_relations_stay_scoped(student, tatu):
    conversation = Conversation.objects.create(user=student, mode="mentor")
    conversation.messages.create(role="user", content="salom")
    with activate(default_institution()):
        assert conversation.messages.count() == 1
    with activate(tatu):
        assert conversation.messages.count() == 0


# ---------------------------------------------------------------- ro'yxatdan o'tish va noyoblik


def register(client, username):
    data = {
        "first_name": "Ali",
        "last_name": "Valiyev",
        "username": username,
        "password1": "Kuchli-parol-2026",
        "password2": "Kuchli-parol-2026",
    }
    return client.post("/register/", data)


def test_registration_attaches_user_to_institution(client, tatu):
    assert register(host(client), "ali_tatu").status_code == 302
    with unscoped():
        assert User.objects.get(username="ali_tatu").institution == tatu


def test_username_is_unique_across_institutions(client, make_user, tatu):
    make_user(username="band_login")
    response = register(host(client), "band_login")
    assert response.status_code == 200
    assert "username" in response.context["form"].errors


def test_registration_stops_at_plan_limit(client, tatu, tatu_user, monkeypatch):
    monkeypatch.setitem(plans.PLANS["standart"], "students", 1)
    tatu_user()
    response = host(client).get("/register/")
    assert response.status_code == 403
    assert "Joylar tugadi" in response.content.decode()


def test_telegram_account_bound_to_one_institution(student, tatu):
    student.telegram_id = 777
    student.save()
    with activate(tatu), pytest.raises(TelegramAuthError):
        get_or_create_telegram_user({"id": 777, "first_name": "Ali"})
    with activate(default_institution()):
        assert get_or_create_telegram_user({"id": 777})[0] == student


# ---------------------------------------------------------------- platforma domeni, holat, tariflar


def test_platform_host_shows_saas_pages_only(client, settings):
    settings.SAAS_BASE_DOMAIN = "talenthub.uz"
    settings.ALLOWED_HOSTS = [".talenthub.uz", "talenthub.uz"]
    host(client, "talenthub.uz")
    assert client.get("/app/")["Location"] == "/saas/"
    assert client.get("/saas/").status_code == 200


def test_unknown_subdomain_and_inactive_institution(client, tatu):
    assert host(client, "yoq.localhost").get("/").status_code == 404
    tatu.is_active = False
    tatu.save()
    response = host(client).get("/")
    assert response.status_code == 503
    assert "vaqtincha yopiq" in response.content.decode()


def test_ai_features_follow_plan(tatu, tatu_user, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test")
    user = tatu_user()
    tatu.plan = "pilot"
    tatu.save()
    conversation = Conversation.objects.create(user=user, mode="mentor")
    with pytest.raises(ai_services.AiUnavailable, match="tarif"):
        ai_services.reply(conversation, "salom")
    with pytest.raises(ai_services.AiUnavailable, match="tarif"):
        ai_services.write_resume(user)


def test_sponsors_page_requires_plan_feature(client, tatu):
    tatu.plan = "pilot"
    tatu.save()
    assert host(client).get("/homiylar/").status_code == 404
    tatu.plan = "standart"
    tatu.save()
    assert host(client).get("/homiylar/").status_code == 200


def test_branding_uses_institution_name_and_colors(client, tatu):
    tatu.color_dark, tatu.color_light = "#123456", "#abcdef"
    tatu.save()
    body = host(client).get("/").content.decode()
    assert "TATU Talent Hub" in body
    assert "--brand: #123456" in body
    assert "ANDTI" not in body


# ---------------------------------------------------------------- SaaS: ariza, tasdiqlash, sozlamalar


def test_saas_request_and_platform_approval(client, make_user):
    response = client.post(
        "/saas/",
        {
            "institution_name": "Farg'ona politexnika instituti",
            "short_name": "FarPI",
            "contact_name": "Rustam Aliyev",
            "phone": "+998901112233",
            "plan": "pilot",
        },
    )
    assert response.status_code == 302
    request_obj = InstitutionRequest.objects.get()

    owner = make_user(username="owner", is_superuser=True, is_staff=True)
    client.force_login(owner)
    page = client.get("/platform/").content.decode()
    assert "politexnika instituti" in page
    client.post(f"/platform/requests/{request_obj.pk}/approve/")
    request_obj.refresh_from_db()
    farpi = Institution.objects.get(slug="farpi")
    assert request_obj.status == "approved" and request_obj.institution == farpi
    with unscoped():
        admin = User.objects.get(username="farpi_admin")
    assert admin.institution == farpi and admin.role == User.Role.RECTOR and admin.is_staff
    assert farpi.paid_until is not None  # pilot muddati


def test_platform_dashboard_is_for_superusers_only(client, make_user):
    client.force_login(make_user(role=User.Role.RECTOR))
    assert client.get("/platform/").status_code == 302


def test_institution_admin_manages_settings_and_faculties(client, tatu):
    with unscoped():
        admin = User.objects.get(username="tatu_admin")
    host(client).force_login(admin)
    assert client.get("/settings/otm/").status_code == 200
    client.post("/settings/otm/", {"form": "faculty", "name": "Telekommunikatsiya fakulteti", "short_name": "TK"})
    client.post(
        "/settings/otm/",
        {
            "form": "settings",
            "name": tatu.name,
            "short_name": "TUIT",
            "tagline": "Kelajak bugun",
            "color_dark": "#111111",
            "color_light": "#222222",
            "registration_open": "on",
            "show_in_league": "on",
        },
    )
    tatu.refresh_from_db()
    assert tatu.short_name == "TUIT" and tatu.color_dark == "#111111"
    with activate(tatu):
        assert Faculty.objects.filter(short_name="TK").exists()
    assert not Faculty.objects.filter(short_name="TK", institution__slug="andti").exists()


def test_student_cannot_open_institution_settings(client, student):
    client.force_login(student)
    assert client.get("/settings/otm/").status_code == 403


def test_tenant_admin_sees_only_own_data_in_admin_panel(client, tatu, tatu_user):
    Reward.objects.create(name="ANDTI sovg'asi", price=10, stock=1)
    with activate(tatu):
        Reward.objects.create(name="TATU sovg'asi", price=10, stock=1)
    with unscoped():
        admin = User.objects.get(username="tatu_admin")
    host(client).force_login(admin)
    page = client.get("/admin/opportunities/reward/").content.decode()
    assert "TATU sovg&#x27;asi" in page and "ANDTI sovg&#x27;asi" not in page
    user_page = client.get(f"/admin/accounts/user/{tatu_user().pk}/change/").content.decode()
    assert "is_superuser" not in user_page


# ---------------------------------------------------------------- statistika va liga


def test_platform_overview_and_league(student, tatu, tatu_user):
    from apps.arena import services as arena

    arena.award(student, "manual", 400, ref="t1")
    arena.award(student, "manual", 100, ref="t2")  # bir nechta tranzaksiya XP'ni ko'paytirib yubormasligi kerak
    other = tatu_user()
    arena.award(other, "manual", 200, ref="t3")
    overview = services.platform_overview()
    rows = {row["obj"].slug: row for row in overview["institutions"]}
    assert rows["andti"]["total_xp"] == 500 and rows["tatu"]["total_xp"] == 200
    assert overview["totals"]["mrr"] == plans.PLANS["premium"]["price"] + plans.PLANS["standart"]["price"]
    league = services.league()
    assert [row["obj"].slug for row in league] == ["andti", "tatu"]


def test_seed_demo_for_another_institution(tatu):
    call_command("seed", "--demo", "--institution", "tatu", verbosity=0)
    with activate(tatu):
        assert User.objects.filter(username="tatu_student1").exists()
        assert Faculty.objects.count() == 3
        assert Reward.objects.count() == 5
    with unscoped():
        assert not User.objects.filter(username="tatu_student1", institution__slug="andti").exists()


def test_api_token_is_rejected_on_other_institution(client, student, tatu):
    from rest_framework_simplejwt.tokens import RefreshToken

    token = str(RefreshToken.for_user(student).access_token)
    headers = {"HTTP_AUTHORIZATION": f"Bearer {token}"}
    assert host(client, "localhost").get("/api/v1/me/", **headers).status_code == 200
    assert host(client).get("/api/v1/me/", **headers).status_code == 401


def test_superuser_adds_institution_from_admin_panel(client, make_user):
    owner = make_user(username="owner", is_superuser=True, is_staff=True)
    client.force_login(owner)
    form = {
        "name": "Farg'ona politexnika instituti",
        "short_name": "FARPI",
        "slug": "farpi",
        "plan": "pilot",
        "color_dark": "#062d3b",
        "color_light": "#168a9c",
        "registration_open": "on",
        "show_in_league": "on",
        "contact_name": "Ali Valiyev",
    }
    response = client.post("/admin/tenants/institution/add/", form, follow=True)
    farpi = Institution.objects.get(slug="farpi")
    assert farpi.paid_until == timezone.localdate() + timedelta(days=90)
    with unscoped():
        admin = User.objects.get(username="farpi_admin")
    assert admin.institution == farpi and admin.role == User.Role.RECTOR and admin.first_name == "Ali"
    assert "farpi_admin" in response.content.decode()

    # Band manzil va band login rad etiladi
    taken = client.post("/admin/tenants/institution/add/", {**form, "slug": "admin"})
    assert taken.status_code == 200 and not Institution.objects.filter(slug="admin").exists()
    dup = client.post("/admin/tenants/institution/add/", {**form, "slug": "farpi2", "admin_username": "farpi_admin"})
    assert dup.status_code == 200 and not Institution.objects.filter(slug="farpi2").exists()

    # Parolni yangilash amali
    old_hash = admin.password
    response = client.post(
        "/admin/tenants/institution/",
        {"action": "reset_admin_password", "_selected_action": [farpi.pk]},
        follow=True,
    )
    admin.refresh_from_db()
    assert admin.password != old_hash and "paroli yangilandi" in response.content.decode()
