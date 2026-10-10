"""Ball iqtisodiyoti: XP va tangalarni berish, sarflash, streak va nishonlar.

Barcha o'zgarishlar faqat shu modul orqali amalga oshiriladi, shunda jurnal va
foydalanuvchidagi qiymatlar doim bir-biriga mos keladi.
"""

from datetime import date, timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.db.models import F, Sum
from django.utils import timezone

from .levels import level_for_xp
from .models import Badge, PointTransaction, Streak, UserBadge

Reason = PointTransaction.Reason

# Har 10 XP uchun 2 tanga
COINS_PER_XP = 0.2
STREAK_BONUS_EVERY = 7
STREAK_BONUS_XP = 50
STREAK_BADGES = {7: "streak-7", 30: "streak-30", 100: "streak-100"}


class InsufficientCoins(Exception):
    pass


def default_coins(xp: int) -> int:
    return int(xp * COINS_PER_XP)


def xp_earned_today(user) -> int:
    start = timezone.localtime().replace(hour=0, minute=0, second=0, microsecond=0)
    total = (
        PointTransaction.objects.filter(user=user, created_at__gte=start)
        .exclude(reason__in=PointTransaction.UNCAPPED_REASONS)
        .aggregate(total=Sum("xp"))["total"]
    )
    return total or 0


@transaction.atomic
def award(user, reason: str, xp: int, coins: int | None = None, ref: str = "", note: str = ""):
    """Foydalanuvchiga ball beradi.

    `ref` berilsa, bir manba uchun ball faqat bir marta beriladi. Agar ball oldin
    berilgan bo'lsa yoki kunlik limit tugagan bo'lsa, `None` qaytaradi.
    """
    if xp < 0:
        raise ValueError("XP manfiy bo'lishi mumkin emas")

    User = get_user_model()
    locked_user = User.objects.select_for_update().get(pk=user.pk)

    if ref and PointTransaction.objects.filter(user=locked_user, reason=reason, ref=ref).exists():
        return None

    if reason not in PointTransaction.UNCAPPED_REASONS:
        remaining = max(settings.ARENA_DAILY_XP_CAP - xp_earned_today(locked_user), 0)
        if remaining == 0:
            return None
        if xp > remaining:
            note = (note + " (kunlik limit)").strip()
            xp = remaining
            coins = None

    if coins is None:
        coins = default_coins(xp)

    level_before = level_for_xp(locked_user.xp)["number"]
    try:
        with transaction.atomic():
            tx = PointTransaction.objects.create(
                user=locked_user, xp=xp, coins=coins, reason=reason, ref=ref, note=note
            )
    except IntegrityError:
        return None

    User.objects.filter(pk=locked_user.pk).update(xp=F("xp") + xp, coins=F("coins") + coins)
    locked_user.refresh_from_db(fields=["xp", "coins"])
    user.xp, user.coins = locked_user.xp, locked_user.coins

    level_after = level_for_xp(locked_user.xp)["number"]
    for number in range(level_before + 1, level_after + 1):
        grant_badge(user, f"level-{number}")
    return tx


@transaction.atomic
def spend_coins(user, amount: int, reason: str = Reason.REDEMPTION, ref: str = "", note: str = ""):
    if amount <= 0:
        raise ValueError("Miqdor musbat bo'lishi kerak")
    User = get_user_model()
    locked_user = User.objects.select_for_update().get(pk=user.pk)
    if locked_user.coins < amount:
        raise InsufficientCoins("Tangalar yetarli emas")
    tx = PointTransaction.objects.create(user=locked_user, xp=0, coins=-amount, reason=reason, ref=ref, note=note)
    User.objects.filter(pk=locked_user.pk).update(coins=F("coins") - amount)
    user.coins = locked_user.coins - amount
    return tx


def grant_badge(user, code: str) -> UserBadge | None:
    """Nishonni beradi. Nishon mavjud bo'lmasa yoki allaqachon berilgan bo'lsa `None`."""
    badge = Badge.objects.filter(code=code).first()
    if badge is None:
        return None
    user_badge, created = UserBadge.objects.get_or_create(user=user, badge=badge)
    if not created:
        return None
    if badge.xp_bonus:
        award(user, Reason.BADGE, badge.xp_bonus, ref=f"badge:{badge.code}", note=badge.name)
    return user_badge


@transaction.atomic
def touch_streak(user, today: date | None = None) -> Streak:
    """Kunlik faollikni qayd qiladi. Har 7 kunda bonus beriladi."""
    today = today or timezone.localdate()
    streak, _ = Streak.objects.select_for_update().get_or_create(user=user)
    if streak.last_active == today:
        return streak
    if streak.last_active == today - timedelta(days=1):
        streak.current += 1
    else:
        streak.current = 1
    streak.longest = max(streak.longest, streak.current)
    streak.last_active = today
    streak.save()

    if streak.current % STREAK_BONUS_EVERY == 0:
        award(
            user,
            Reason.STREAK,
            STREAK_BONUS_XP,
            ref=f"streak:{today.isoformat()}",
            note=f"{streak.current} kunlik streak",
        )
    if streak.current in STREAK_BADGES:
        grant_badge(user, STREAK_BADGES[streak.current])
    return streak


def semester_start(today: date | None = None) -> date:
    """Kuzgi semestr 1-sentabrdan, bahorgi 1-fevraldan boshlanadi."""
    today = today or timezone.localdate()
    if today.month >= 9:
        return date(today.year, 9, 1)
    if today.month >= 2:
        return date(today.year, 2, 1)
    return date(today.year - 1, 9, 1)
