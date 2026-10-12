import pytest

from apps.accounts.models import User
from apps.arena import services as arena
from apps.opportunities import services
from apps.opportunities.models import Reward, Sponsor


@pytest.fixture
def sponsor(db):
    return Sponsor.objects.create(name="TexnoSoft", slug="texnosoft", description="Dasturiy ta'minot kompaniyasi")


@pytest.fixture
def book(sponsor):
    return Reward.objects.create(name="Kitob", price=50, stock=3, emoji="📚", sponsor=sponsor)


def test_initials_for_logo_fallback():
    assert Sponsor(name="Andijon Mexanika Zavodi").initials == "AM"
    assert Sponsor(name="TexnoSoft (demo)").initials == "TD"


def test_shop_shows_sponsor_badge(client, student, book):
    client.force_login(student)
    body = client.get("/shop/").content.decode()
    assert "TexnoSoft</b> homiyligida" in body
    assert "/homiylar/#texnosoft" in body


def test_inactive_sponsor_is_hidden_in_shop(client, student, book, sponsor):
    sponsor.is_active = False
    sponsor.save()
    client.force_login(student)
    assert "homiyligida" not in client.get("/shop/").content.decode()


def test_sponsor_totals_count_only_sponsored_gifts(student, book):
    arena.award(student, "manual", 1000, ref="test")
    plain = Reward.objects.create(name="Talon", price=10, stock=5)
    services.redeem(book, student)
    services.redeem(plain, student)
    totals = services.sponsor_totals()
    assert totals["gifts"] == 1
    assert totals["coins"] == 50
    assert totals["top"][0] == {"name": "TexnoSoft", "gifts": 1}


def test_sponsors_page_is_public_with_contact(client, book, settings):
    settings.SPONSOR_CONTACT = "@startaplar_klubi"
    body = client.get("/homiylar/").content.decode()
    assert "TexnoSoft" in body
    assert "📚 Kitob" in body
    assert "https://t.me/startaplar_klubi" in body


def test_landing_lists_sponsors(client, sponsor):
    body = client.get("/").content.decode()
    assert "Homiylarimiz" in body and "TexnoSoft" in body


def test_rector_insights_show_sponsor_contribution(client, make_user, book):
    rector = make_user(role=User.Role.RECTOR)
    client.force_login(rector)
    body = client.get("/insights/").content.decode()
    assert "Homiylar hissasi" in body


def test_reward_api_includes_sponsor(api, student, book):
    data = api(student).get("/api/v1/rewards/").data
    row = next(r for r in data if r["name"] == "Kitob")
    assert row["sponsor"]["name"] == "TexnoSoft"
