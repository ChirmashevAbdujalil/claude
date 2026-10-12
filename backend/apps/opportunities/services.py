from django.db import IntegrityError, transaction
from django.db.models import Count, F, IntegerField, Prefetch, Q, Sum, Value
from django.db.models.functions import Coalesce
from django.utils import timezone

from apps.arena import services as arena
from apps.arena.levels import level_for_xp

from .models import Application, Opportunity, Redemption, Reward, Sponsor


class OpportunityError(Exception):
    pass


def apply(opportunity: Opportunity, user, motivation: str) -> Application:
    if not opportunity.is_active or (opportunity.deadline and opportunity.deadline < timezone.now()):
        raise OpportunityError("Ariza qabul qilish yakunlangan")
    level = level_for_xp(user.xp)["number"]
    if level < opportunity.min_level:
        raise OpportunityError(f"Bu imkoniyat {opportunity.min_level}-darajadan boshlab ochiladi")
    try:
        with transaction.atomic():
            return Application.objects.create(opportunity=opportunity, user=user, motivation=motivation)
    except IntegrityError as exc:
        raise OpportunityError("Siz allaqachon ariza topshirgansiz") from exc


@transaction.atomic
def redeem(reward: Reward, user) -> Redemption:
    reward = Reward.objects.select_for_update().get(pk=reward.pk)
    if not reward.is_active or reward.stock == 0:
        raise OpportunityError("Mukofot tugagan")
    redemption = Redemption.objects.create(user=user, reward=reward, price=reward.price)
    try:
        arena.spend_coins(user, reward.price, ref=f"redemption:{redemption.pk}", note=reward.name)
    except arena.InsufficientCoins as exc:
        raise OpportunityError("Tangalar yetarli emas") from exc
    Reward.objects.filter(pk=reward.pk).update(stock=F("stock") - 1)
    return redemption


def active_sponsors():
    """Faol homiylar: har biri sotuvdagi sovg'alari va talabalarga berilgan sovg'alar soni bilan."""
    return (
        Sponsor.objects.filter(is_active=True)
        .annotate(
            gifts_given=Count("rewards__redemptions", distinct=True),
            coins_value=Coalesce(Sum("rewards__redemptions__price"), Value(0), output_field=IntegerField()),
        )
        .prefetch_related(Prefetch("rewards", queryset=Reward.objects.filter(is_active=True), to_attr="on_sale"))
    )


def sponsor_totals(user_ids=None) -> dict:
    """Homiylar hissasi: nechta sovg'a ularning hisobidan berilgan va qancha tangaga teng."""
    redemptions = Redemption.objects.filter(reward__sponsor__isnull=False)
    if user_ids is not None:
        redemptions = redemptions.filter(user_id__in=user_ids)
    agg = redemptions.aggregate(gifts=Count("id"), coins=Coalesce(Sum("price"), Value(0)))
    top = (
        Sponsor.objects.filter(is_active=True)
        .annotate(
            gifts=Count(
                "rewards__redemptions",
                filter=Q(rewards__redemptions__in=redemptions),
                distinct=True,
            )
        )
        .order_by("-gifts", "order", "name")
    )
    return {
        "sponsors": Sponsor.objects.filter(is_active=True).count(),
        "sponsored_rewards": Reward.objects.filter(is_active=True, sponsor__is_active=True).count(),
        "gifts": agg["gifts"],
        "coins": agg["coins"],
        "top": [{"name": s.name, "gifts": s.gifts} for s in top[:5]],
    }
