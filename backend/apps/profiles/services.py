from django.db import transaction
from django.db.models import Avg

from apps.arena import services as arena

from .models import Achievement, Endorsement, Skill, UserSkill

ENDORSEMENT_XP = 30


class ReviewError(Exception):
    pass


@transaction.atomic
def endorse(user_skill: UserSkill, teacher, comment: str = "") -> Endorsement:
    if user_skill.user_id == teacher.id:
        raise ReviewError("O'z ko'nikmangizni tasdiqlay olmaysiz")
    endorsement, created = Endorsement.objects.get_or_create(
        user_skill=user_skill, endorsed_by=teacher, defaults={"comment": comment}
    )
    if not created:
        raise ReviewError("Siz bu ko'nikmani allaqachon tasdiqlagansiz")
    arena.award(
        user_skill.user,
        arena.Reason.ENDORSEMENT,
        ENDORSEMENT_XP,
        ref=f"endorsement:{endorsement.pk}",
        note=user_skill.skill.name,
    )
    if user_skill.endorsements.count() == 1:
        arena.grant_badge(user_skill.user, "first-endorsement")
    return endorsement


@transaction.atomic
def review_achievement(
    achievement: Achievement, reviewer, approve: bool, xp: int | None = None, comment: str = ""
) -> Achievement:
    achievement = Achievement.objects.select_for_update().get(pk=achievement.pk)
    if achievement.status != Achievement.Status.PENDING:
        raise ReviewError("Bu yutuq allaqachon ko'rib chiqilgan")
    if achievement.user_id == reviewer.id:
        raise ReviewError("O'z yutug'ingizni tasdiqlay olmaysiz")

    achievement.reviewed_by = reviewer
    achievement.review_comment = comment
    if approve:
        if xp is None:
            xp = Achievement.DEFAULT_XP.get(achievement.kind, 50)
        xp = max(0, min(xp, Achievement.MAX_XP))
        achievement.status = Achievement.Status.APPROVED
        achievement.xp_awarded = xp
        arena.award(
            achievement.user,
            arena.Reason.ACHIEVEMENT,
            xp,
            ref=f"achievement:{achievement.pk}",
            note=achievement.title,
        )
        if achievement.kind == Achievement.Kind.HACKATHON:
            arena.grant_badge(achievement.user, "hackathon")
        if achievement.kind == Achievement.Kind.PATENT:
            arena.grant_badge(achievement.user, "inventor")
    else:
        achievement.status = Achievement.Status.REJECTED
    achievement.save()
    return achievement


def skill_map(user) -> list[dict]:
    """Ko'nikmalar xaritasi (radar diagramma uchun): har bir yo'nalish bo'yicha o'rtacha daraja."""
    averages = dict(
        UserSkill.objects.filter(user=user)
        .values_list("skill__category")
        .annotate(avg=Avg("level"))
        .values_list("skill__category", "avg")
    )
    return [
        {"category": value, "label": label, "score": round(averages.get(value, 0) or 0, 2)}
        for value, label in Skill.Category.choices
    ]
