"""Rektorat va dekanat uchun statistika."""

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.db.models import Avg, Count, IntegerField, Q, Sum, Value
from django.db.models.functions import Coalesce
from django.utils import timezone

from apps.accounts.models import Faculty
from apps.arena.levels import LEVELS
from apps.discovery.models import Challenge, Submission, TalentFlag
from apps.opportunities.models import Application, Opportunity
from apps.opportunities.services import sponsor_totals
from apps.profiles.models import Achievement
from apps.projects.models import Project

TOP_SIZE = 10


def _student_brief(user, score=None) -> dict:
    return {
        "id": user.id,
        "full_name": user.get_full_name() or user.username,
        "faculty": user.faculty.short_name if user.faculty else None,
        "course": user.course,
        "xp": user.xp if score is None else score,
    }


def dashboard(viewer) -> dict:
    User = get_user_model()
    now = timezone.now()
    week_ago = now - timedelta(days=7)
    month_ago = now - timedelta(days=30)

    students = User.objects.filter(role=User.Role.STUDENT, is_active=True)
    faculties = Faculty.objects.all()
    # Dekan faqat o'z fakultetini ko'radi
    if viewer.role == User.Role.DEAN and viewer.faculty_id:
        students = students.filter(faculty_id=viewer.faculty_id)
        faculties = faculties.filter(pk=viewer.faculty_id)
    student_ids = students.values("id")

    active_week = students.filter(transactions__created_at__gte=week_ago).distinct().count()

    level_distribution = []
    for index, (number, name, min_xp) in enumerate(LEVELS):
        upper = LEVELS[index + 1][2] if index + 1 < len(LEVELS) else None
        qs = students.filter(xp__gte=min_xp)
        if upper is not None:
            qs = qs.filter(xp__lt=upper)
        level_distribution.append({"level": number, "name": name, "count": qs.count()})

    by_faculty = [
        {
            "faculty_id": f.id,
            "faculty": f.name,
            "students": f.student_count,
            "total_xp": f.total_xp,
            "avg_xp": round(f.avg_xp or 0, 1),
        }
        for f in faculties.annotate(
            student_count=Count("users", filter=Q(users__role=User.Role.STUDENT), distinct=True),
            total_xp=Coalesce(
                Sum("users__xp", filter=Q(users__role=User.Role.STUDENT)), Value(0), output_field=IntegerField()
            ),
            avg_xp=Avg("users__xp", filter=Q(users__role=User.Role.STUDENT)),
        ).order_by("-total_xp")
    ]

    top_students = [_student_brief(u) for u in students.select_related("faculty").order_by("-xp")[:TOP_SIZE]]

    # «Yashirin iqtidorlar»: oxirgi 30 kunda eng tez o'sayotgan talabalar
    rising = (
        students.annotate(
            gained=Coalesce(
                Sum("transactions__xp", filter=Q(transactions__created_at__gte=month_ago)),
                Value(0),
                output_field=IntegerField(),
            )
        )
        .filter(gained__gt=0)
        .select_related("faculty")
        .order_by("-gained")[:TOP_SIZE]
    )
    rising_stars = [_student_brief(u, score=u.gained) for u in rising]

    recent_flags = [
        {
            "student": _student_brief(flag.student),
            "area": flag.get_area_display(),
            "note": flag.note,
            "flagged_by": flag.flagged_by.get_full_name() or flag.flagged_by.username,
            "created_at": flag.created_at,
        }
        for flag in TalentFlag.objects.filter(student_id__in=student_ids).select_related(
            "student", "student__faculty", "flagged_by"
        )[:TOP_SIZE]
    ]

    projects = Project.objects.filter(owner_id__in=student_ids)
    projects_by_stage = {row["stage"]: row["count"] for row in projects.values("stage").annotate(count=Count("id"))}

    return {
        "generated_at": now,
        "totals": {
            "students": students.count(),
            "active_last_7_days": active_week,
            "open_challenges": Challenge.objects.filter(
                is_published=True, starts_at__lte=now, ends_at__gte=now
            ).count(),
            "pending_submissions": Submission.objects.filter(
                status=Submission.Status.PENDING, user_id__in=student_ids
            ).count(),
            "pending_achievements": Achievement.objects.filter(
                status=Achievement.Status.PENDING, user_id__in=student_ids
            ).count(),
            "approved_achievements": Achievement.objects.filter(
                status=Achievement.Status.APPROVED, user_id__in=student_ids
            ).count(),
            "projects": projects.count(),
            "active_opportunities": Opportunity.objects.filter(is_active=True).count(),
            "applications": Application.objects.filter(user_id__in=student_ids).count(),
        },
        "projects_by_stage": projects_by_stage,
        "level_distribution": level_distribution,
        "by_faculty": by_faculty,
        "top_students": top_students,
        "rising_stars": rising_stars,
        "recent_talent_flags": recent_flags,
        "sponsors": sponsor_totals(student_ids),
    }
