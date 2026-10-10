from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Count, Q

from apps.arena import services as arena

from .models import Project, ProjectMember

STAGE_XP = 100
RECOMMENDATION_LIMIT = 10


class ProjectError(Exception):
    pass


@transaction.atomic
def create_project(owner, **data) -> Project:
    skills = data.pop("skills_needed", [])
    project = Project.objects.create(owner=owner, **data)
    project.skills_needed.set(skills)
    ProjectMember.objects.create(project=project, user=owner, role="Asoschi", status=ProjectMember.Status.ACTIVE)
    return project


def request_join(project: Project, user, role: str = "A'zo", message: str = "") -> ProjectMember:
    if not project.is_recruiting:
        raise ProjectError("Loyiha hozir a'zo qabul qilmayapti")
    member, created = ProjectMember.objects.get_or_create(
        project=project, user=user, defaults={"role": role, "message": message}
    )
    if not created:
        raise ProjectError("Siz allaqachon so'rov yuborgansiz yoki a'zosiz")
    return member


def approve_member(project: Project, actor, member_id: int) -> ProjectMember:
    if project.owner_id != actor.id:
        raise ProjectError("Faqat loyiha asoschisi a'zolarni qabul qiladi")
    member = ProjectMember.objects.filter(project=project, pk=member_id, status=ProjectMember.Status.PENDING).first()
    if member is None:
        raise ProjectError("So'rov topilmadi")
    member.status = ProjectMember.Status.ACTIVE
    member.save(update_fields=["status"])
    arena.grant_badge(member.user, "team-player")
    return member


@transaction.atomic
def advance_stage(project: Project, actor) -> Project:
    """Loyihani keyingi bosqichga o'tkazadi va barcha faol a'zolarga XP beradi."""
    project = Project.objects.select_for_update().get(pk=project.pk)
    if project.owner_id != actor.id and not actor.is_reviewer:
        raise ProjectError("Faqat asoschi yoki o'qituvchi bosqichni o'zgartira oladi")
    next_stage = project.next_stage
    if next_stage is None:
        raise ProjectError("Loyiha oxirgi bosqichda")
    project.stage = next_stage
    project.save(update_fields=["stage", "updated_at"])

    for member in project.members.filter(status=ProjectMember.Status.ACTIVE).select_related("user"):
        arena.award(
            member.user,
            arena.Reason.PROJECT,
            STAGE_XP,
            ref=f"project:{project.pk}:{next_stage}",
            note=f"{project.title}: {project.get_stage_display()}",
        )
    if next_stage == Project.Stage.STARTUP:
        arena.grant_badge(project.owner, "startup-founder")
    return project


def recommend_teammates(project: Project, limit: int = RECOMMENDATION_LIMIT):
    """Loyihaga kerakli ko'nikmalarga ega talabalarni tavsiya qiladi.

    Mos ko'nikmalar soni, keyin tasdiqlangan ko'nikmalar va XP bo'yicha saralanadi.
    """
    User = get_user_model()
    skill_ids = list(project.skills_needed.values_list("id", flat=True))
    if not skill_ids:
        return User.objects.none()
    member_ids = project.members.values_list("user_id", flat=True)
    return (
        User.objects.filter(role=User.Role.STUDENT, is_active=True, skills__skill_id__in=skill_ids)
        .exclude(pk__in=member_ids)
        .annotate(
            matched=Count("skills", filter=Q(skills__skill_id__in=skill_ids), distinct=True),
            endorsed=Count("skills__endorsements", filter=Q(skills__skill_id__in=skill_ids), distinct=True),
        )
        .select_related("faculty")
        .order_by("-matched", "-endorsed", "-xp")[:limit]
    )
