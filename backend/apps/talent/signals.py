"""Reyestrni avtomatik to'ldirish va imkoniyatlarni mos talabalarga yetkazish."""

from django.db import transaction
from django.db.models.signals import post_delete, post_save

from .tracks import FROM_ACHIEVEMENT, FROM_SKILL, RESULT_KINDS


def _flag_saved(sender, instance, created, raw=False, **kwargs):
    """O'qituvchi «uchqun» belgisini qo'ydi: talaba reyestrga tushadi."""
    if raw or not created:
        return
    from . import services
    from .models import TalentProfile

    note = f"{instance.flagged_by}: {instance.note}".strip()
    services.ensure_profile(
        instance.student,
        source=TalentProfile.Source.FLAG,
        track=FROM_SKILL.get(instance.area, ""),
        by=instance.flagged_by,
        note=note[:500],
    )


def _achievement_saved(sender, instance, raw=False, **kwargs):
    """Olimpiada, hakaton, maqola yoki patent tasdiqlandi: talaba reyestrga, holati «Natijaga erishgan»."""
    if raw or instance.status != "approved" or instance.kind not in RESULT_KINDS:
        return
    from . import services
    from .models import TalentProfile

    if instance.user.role != "student":
        return
    services.ensure_profile(
        instance.user, source=TalentProfile.Source.ACHIEVEMENT, track=FROM_ACHIEVEMENT.get(instance.kind, "")
    )


def _goal_changed(sender, instance, raw=False, **kwargs):
    if raw:
        return
    from . import services
    from .models import TalentProfile

    profile = TalentProfile.objects.filter(pk=instance.profile_id).first()
    if profile is not None:
        services.refresh_status(profile)


def _opportunity_saved(sender, instance, created, raw=False, **kwargs):
    if raw or not created or not instance.is_active:
        return
    from . import services

    transaction.on_commit(lambda: services.notify_matches(instance))


def connect():
    from apps.discovery.models import TalentFlag
    from apps.opportunities.models import Opportunity
    from apps.profiles.models import Achievement

    from .models import DevelopmentGoal

    post_save.connect(_flag_saved, sender=TalentFlag, dispatch_uid="talent:flag")
    post_save.connect(_achievement_saved, sender=Achievement, dispatch_uid="talent:achievement")
    post_save.connect(_goal_changed, sender=DevelopmentGoal, dispatch_uid="talent:goal-save")
    post_delete.connect(_goal_changed, sender=DevelopmentGoal, dispatch_uid="talent:goal-delete")
    post_save.connect(_opportunity_saved, sender=Opportunity, dispatch_uid="talent:opportunity")
