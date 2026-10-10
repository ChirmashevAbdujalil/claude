from django.db import IntegrityError, transaction
from django.db.models import F
from django.utils import timezone

from apps.arena import services as arena
from apps.arena.levels import level_for_xp

from .models import Application, Opportunity, Redemption, Reward


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
