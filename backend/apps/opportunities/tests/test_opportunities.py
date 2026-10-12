from datetime import timedelta

from django.utils import timezone

from apps.accounts.models import User
from apps.arena import services as arena
from apps.opportunities.models import Opportunity, Reward

MOTIVATION = "Men bu stajirovkada real loyihalarda tajriba orttirmoqchiman."


def make_opportunity(creator, **kwargs):
    kwargs.setdefault("kind", Opportunity.Kind.INTERNSHIP)
    kwargs.setdefault("title", "Stajirovka")
    kwargs.setdefault("description", "Tavsif")
    kwargs.setdefault("organization", "IT Park")
    return Opportunity.objects.create(created_by=creator, **kwargs)


def test_partner_can_publish_student_cannot(api, student, make_user):
    partner = make_user(role=User.Role.PARTNER)
    payload = {"kind": "vacancy", "title": "Junior Python", "description": "Tavsif", "organization": "Hamkor"}
    assert api(student).post("/api/v1/opportunities/", payload, format="json").status_code == 403
    assert api(partner).post("/api/v1/opportunities/", payload, format="json").status_code == 201


def test_apply_respects_min_level(api, student, teacher):
    opportunity = make_opportunity(teacher, min_level=2)
    client = api(student)
    url = f"/api/v1/opportunities/{opportunity.id}/apply/"
    assert client.post(url, {"motivation": MOTIVATION}, format="json").status_code == 400

    arena.award(student, arena.Reason.MANUAL, 500)
    assert client.post(url, {"motivation": MOTIVATION}, format="json").status_code == 201
    assert client.post(url, {"motivation": MOTIVATION}, format="json").status_code == 400
    assert client.get("/api/v1/opportunities/").data["results"][0]["applied"] is True


def test_expired_opportunity_hidden(api, student, teacher):
    make_opportunity(teacher, deadline=timezone.now() - timedelta(days=1))
    assert api(student).get("/api/v1/opportunities/").data["count"] == 0


def test_redeem_reward(api, student):
    reward = Reward.objects.get(name="Oshxona taloni")
    client = api(student)
    assert client.post(f"/api/v1/rewards/{reward.id}/redeem/").status_code == 400

    arena.award(student, arena.Reason.MANUAL, 300)  # 60 tanga
    response = client.post(f"/api/v1/rewards/{reward.id}/redeem/")
    assert response.status_code == 201
    student.refresh_from_db()
    reward.refresh_from_db()
    assert student.coins == 10
    assert reward.stock == 99
    assert len(client.get("/api/v1/me/redemptions/").data["results"]) == 1


def test_out_of_stock(api, student):
    reward = Reward.objects.create(name="Noyob", price=1, stock=0)
    arena.award(student, arena.Reason.MANUAL, 100)
    assert api(student).post(f"/api/v1/rewards/{reward.id}/redeem/").status_code == 400


def test_shop_shows_reward_emoji(client, make_user):
    Reward.objects.update_or_create(name="Texnik kitob", defaults={"price": 150, "stock": 3, "emoji": "📚"})
    client.force_login(make_user())
    body = client.get("/shop/").content.decode()
    assert "📚" in body
