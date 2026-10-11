import math

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.db.models import Q, Sum
from django.shortcuts import render

from apps.arena import services as arena
from apps.arena.models import Badge, PointTransaction
from apps.community.models import Event
from apps.discovery.models import Challenge
from apps.opportunities.models import Reward
from apps.profiles.models import Achievement
from apps.profiles.services import ENDORSEMENT_XP
from apps.projects.services import STAGE_XP

FAQ = [
    (
        "Tangalarning muddati tugaydimi?",
        "Yo'q. Yig'gan tangalaringiz sarflamaguningizcha hisobingizda saqlanadi.",
    ),
    (
        "Tanga sarflasam darajam yoki reytingim tushadimi?",
        "Yo'q. Daraja va reyting XP bo'yicha hisoblanadi, XP esa hech qachon kamaymaydi. "
        "Tanga sarflash faqat tanga balansini kamaytiradi.",
    ),
    (
        "Tangalarni do'stimga o'tkazsam bo'ladimi?",
        "Yo'q. Tangalar shaxsiy: ular faqat o'zingizning harakatlaringiz uchun beriladi.",
    ),
    (
        "Sovg'ani qanday olaman?",
        "Do'konda «Olish» tugmasini bosing. Xarid «Tayyorlanmoqda» holatida paydo bo'ladi. "
        "Sovg'ani talabalar bilan ishlash bo'limidan olasiz, topshirilgach holati «Topshirildi» ga o'zgaradi.",
    ),
    (
        "Mukofot tugab qolsa-chi?",
        "Zaxira tugagan mukofotni olib bo'lmaydi, tangalaringiz esa joyida qoladi. "
        "Mukofotlar muntazam to'ldirib boriladi.",
    ),
    (
        "Tangani sotib olsa bo'ladimi?",
        "Yo'q. Tanga faqat platformadagi faollik uchun beriladi: shuning uchun u haqiqiy yutuqni bildiradi.",
    ),
]


def _coins(xp: int) -> int:
    return arena.default_coins(xp)


@login_required
def coins(request):
    """Tangalar bo'limi: ular nima beradi, qanday yig'iladi va nimaga sarflanadi."""
    user = request.user
    balance = user.coins

    event_xp = Event._meta.get_field("xp_reward").default
    kinds = dict(Challenge.Kind.choices)
    earn_rows = [("🎯", f"{kinds[k]} challenge", _coins(xp)) for k, xp in Challenge.DEFAULT_XP.items()]
    earn_rows += [
        ("🎓", "O'qituvchi ko'nikmangizni tasdiqlasa", _coins(ENDORSEMENT_XP)),
        ("📅", "Tadbirda qatnashish", _coins(event_xp)),
        ("🚀", "Loyiha keyingi bosqichga o'tsa", _coins(STAGE_XP)),
        ("🔥", f"Har {arena.STREAK_BONUS_EVERY} kunlik streak", _coins(arena.STREAK_BONUS_XP)),
    ]
    achievement_coins = [_coins(xp) for xp in Achievement.DEFAULT_XP.values()]
    badge_coins = [_coins(b.xp_bonus) for b in Badge.objects.filter(xp_bonus__gt=0)]

    rewards = list(Reward.objects.filter(is_active=True).order_by("price"))
    for reward in rewards:
        reward.available = reward.stock > 0
        reward.affordable = reward.available and balance >= reward.price
        reward.missing = max(reward.price - balance, 0)
    next_goal = next((r for r in rewards if r.available and r.price > balance), None)
    goal = None
    if next_goal:
        daily_coins = _coins(Challenge.DEFAULT_XP[Challenge.Kind.DAILY]) or 1
        weekly_coins = _coins(Challenge.DEFAULT_XP[Challenge.Kind.WEEKLY]) or 1
        goal = {
            "reward": next_goal,
            "missing": next_goal.missing,
            "percent": min(100, round(balance / next_goal.price * 100)) if next_goal.price else 100,
            "weekly": math.ceil(next_goal.missing / weekly_coins),
            "daily": math.ceil(next_goal.missing / daily_coins),
        }

    history = PointTransaction.objects.filter(user=user).exclude(coins=0)[:10]
    totals = PointTransaction.objects.filter(user=user).aggregate(
        earned=Sum("coins", filter=Q(coins__gt=0)), spent=Sum("coins", filter=Q(coins__lt=0))
    )
    earned, spent = totals["earned"] or 0, -(totals["spent"] or 0)

    return render(
        request,
        "web/coins.html",
        {
            "balance": balance,
            "earned": earned,
            "spent": spent,
            "coins_per_10": _coins(10),
            "daily_cap_coins": _coins(settings.ARENA_DAILY_XP_CAP),
            "earn_rows": earn_rows,
            "achievement_range": (min(achievement_coins), max(achievement_coins)) if achievement_coins else None,
            "badge_range": (min(badge_coins), max(badge_coins)) if badge_coins else None,
            "rewards": rewards,
            "affordable_count": sum(1 for r in rewards if r.affordable),
            "goal": goal,
            "history": history,
            "faq": FAQ,
        },
    )
