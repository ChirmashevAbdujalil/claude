from django.test import Client
from django.urls import reverse

from apps.arena import services as arena
from apps.opportunities.models import Reward
from apps.opportunities.services import redeem


def page(user):
    client = Client()
    client.force_login(user)
    return client.get(reverse("web:coins"))


def test_coins_page_requires_login():
    response = Client().get(reverse("web:coins"))
    assert response.status_code == 302


def test_coins_page_explains_earning_and_spending(student):
    html = page(student).content.decode()
    assert "Tangalar nima va ular nima beradi?" in html
    assert "har 10 XP uchun 2 tanga" in html
    # Haftalik challenge 50 XP = 10 tanga, oylik 300 XP = 60 tanga
    assert "+10 🪙" in html and "+60 🪙" in html
    # Barcha faol mukofotlar ko'rsatiladi
    for reward in Reward.objects.filter(is_active=True):
        assert reward.name in html
    assert "Tangalarning muddati tugaydimi?" in html


def test_next_goal_progress(student):
    arena.award(student, arena.Reason.MANUAL, 200)  # 40 tanga
    response = page(student)
    goal = response.context["goal"]
    assert goal["reward"].name == "Oshxona taloni"  # 50 tanga
    assert goal["missing"] == 10
    assert goal["percent"] == 80
    assert goal["weekly"] == 1 and goal["daily"] == 5
    assert "Yana <b>10 tanga</b> kerak" in response.content.decode()


def test_affordable_rewards_and_history(student):
    arena.award(student, arena.Reason.MANUAL, 1000)  # 200 tanga
    redeem(Reward.objects.get(name="Oshxona taloni"), student)  # -50
    response = page(student)
    assert response.context["earned"] == 200
    assert response.context["spent"] == 50
    assert response.context["balance"] == 150
    assert response.context["goal"]["reward"].name == "Talent Hub futbolkasi"
    html = response.content.decode()
    assert "Tangangiz yetadi" in html
    assert "-50 🪙" in html


def test_out_of_stock_reward_is_not_a_goal(student):
    Reward.objects.filter(name="Oshxona taloni").update(stock=0)
    response = page(student)
    assert response.context["goal"]["reward"].name == "Texnik kitob"
    assert "Hozircha tugagan" in response.content.decode()


def test_coins_linked_from_layout(student):
    client = Client()
    client.force_login(student)
    html = client.get(reverse("web:shop")).content.decode()
    assert reverse("web:coins") in html
