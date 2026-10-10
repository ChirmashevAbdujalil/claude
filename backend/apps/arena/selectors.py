"""Reyting va liga hisob-kitoblari: API va veb-interfeys uchun umumiy."""

from dataclasses import dataclass
from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.db.models import Count, IntegerField, Q, Sum, Value
from django.db.models.functions import Coalesce
from django.utils import timezone

from apps.accounts.models import Faculty

from .services import semester_start

LEADERBOARD_SIZE = 50
PERIODS = {"week": 7, "month": 30}


@dataclass
class LeaderboardRow:
    rank: int
    user: object
    score: int


@dataclass
class Leaderboard:
    period: str
    rows: list[LeaderboardRow]
    me: LeaderboardRow | None


def leaderboard(viewer, period: str = "all", faculty: str | None = None, course: str | None = None) -> Leaderboard:
    User = get_user_model()
    users = User.objects.filter(role=User.Role.STUDENT, is_active=True, is_public=True)
    if faculty and str(faculty).isdigit():
        users = users.filter(faculty_id=int(faculty))
    if course and str(course).isdigit():
        users = users.filter(course=int(course))

    if period in PERIODS:
        since = timezone.now() - timedelta(days=PERIODS[period])
        users = users.annotate(
            score=Coalesce(
                Sum("transactions__xp", filter=Q(transactions__created_at__gte=since)),
                Value(0),
                output_field=IntegerField(),
            )
        ).filter(score__gt=0)
    else:
        period = "all"
        users = users.annotate(score=Coalesce("xp", Value(0)))

    top = users.select_related("faculty").order_by("-score", "id")[:LEADERBOARD_SIZE]
    rows = [LeaderboardRow(rank=i, user=u, score=u.score) for i, u in enumerate(top, start=1)]

    me = next((row for row in rows if row.user.id == viewer.id), None)
    if me is None:
        mine = users.filter(pk=viewer.pk).first()
        if mine is not None:
            rank = users.filter(Q(score__gt=mine.score) | Q(score=mine.score, id__lt=mine.id)).count() + 1
            me = LeaderboardRow(rank=rank, user=mine, score=mine.score)
    return Leaderboard(period=period, rows=rows, me=me)


def faculty_league() -> tuple[date, list[dict]]:
    """Fakultetlar ligasi: joriy semestrda to'plangan XP."""
    since = semester_start()
    faculties = Faculty.objects.annotate(
        score=Coalesce(
            Sum("users__transactions__xp", filter=Q(users__transactions__created_at__date__gte=since)),
            Value(0),
            output_field=IntegerField(),
        ),
        members=Count("users", filter=Q(users__role="student"), distinct=True),
    ).order_by("-score", "name")
    results = [
        {
            "rank": i,
            "faculty_id": f.id,
            "faculty": f.name,
            "short_name": f.short_name,
            "xp": f.score,
            "members": f.members,
        }
        for i, f in enumerate(faculties, start=1)
    ]
    return since, results
