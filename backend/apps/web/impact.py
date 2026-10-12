"""«Natijalar» sahifasi uchun OTM ko'rsatkichlari: o'sish, faollik, qamrov va natijalar.

Faqat umumlashgan raqamlar: hech bir talabaning ismi yoki shaxsiy ma'lumoti chiqmaydi.
Barcha so'rovlar joriy OTM bilan cheklangan (TenantManager), natija qisqa muddat keshlanadi.
"""

from datetime import timedelta

from django.core.cache import cache
from django.db.models import Count, Sum
from django.db.models.functions import TruncWeek
from django.utils import timezone

from apps.accounts.models import Faculty, User
from apps.ai.models import Conversation
from apps.arena.models import PointTransaction, UserBadge
from apps.community.models import Event, EventRegistration
from apps.discovery.models import Challenge, Submission
from apps.opportunities.models import Application, Redemption, Sponsor
from apps.profiles.models import Achievement, Endorsement
from apps.projects.models import Project, ProjectMember

WEEKS = 12
CACHE_SECONDS = 300
# Faollik turlari grafigida ko'rsatilmaydigan sabablar: qo'lda berilgan ball va sovg'a xaridi faollik emas
MIX_EXCLUDE = {PointTransaction.Reason.MANUAL, PointTransaction.Reason.REDEMPTION}
MONTHS = ["yan", "fev", "mar", "apr", "may", "iyun", "iyul", "avg", "sen", "okt", "noy", "dek"]


def _week_label(day) -> str:
    return f"{day.day} {MONTHS[day.month - 1]}"


def _students():
    return User.objects.filter(role=User.Role.STUDENT, is_active=True, is_superuser=False)


def _active_pairs(since):
    """(hafta boshi, talaba id) juftlari: ball olgan yoki yechim yuborgan talabalar."""
    pairs = set()
    sources = [
        PointTransaction.objects.filter(user__role=User.Role.STUDENT).exclude(reason__in=MIX_EXCLUDE),
        Submission.objects.filter(user__role=User.Role.STUDENT),
    ]
    for qs in sources:
        rows = qs.filter(created_at__gte=since).annotate(week=TruncWeek("created_at")).values_list("week", "user_id")
        pairs.update((week.date() if hasattr(week, "date") else week, user_id) for week, user_id in rows.distinct())
    return pairs


def _active_since(since) -> set:
    ids = set(
        PointTransaction.objects.filter(created_at__gte=since, user__role=User.Role.STUDENT)
        .exclude(reason__in=MIX_EXCLUDE)
        .values_list("user_id", flat=True)
    )
    ids |= set(Submission.objects.filter(created_at__gte=since).values_list("user_id", flat=True))
    ids |= set(_students().filter(last_login__gte=since).values_list("id", flat=True))
    return ids


def _weekly(now):
    today = timezone.localdate(now)
    this_monday = today - timedelta(days=today.weekday())
    weeks = [this_monday - timedelta(weeks=WEEKS - 1 - i) for i in range(WEEKS)]
    start = timezone.make_aware(timezone.datetime.combine(weeks[0], timezone.datetime.min.time()))

    students = _students()
    before = students.filter(date_joined__lt=start).count()
    joined = {
        (row["week"].date() if hasattr(row["week"], "date") else row["week"]): row["n"]
        for row in students.filter(date_joined__gte=start)
        .annotate(week=TruncWeek("date_joined"))
        .values("week")
        .annotate(n=Count("id"))
    }
    active = {}
    for week, user_id in _active_pairs(start):
        active.setdefault(week, set()).add(user_id)

    rows, total = [], before
    for monday in weeks:
        total += joined.get(monday, 0)
        rows.append(
            {
                "label": _week_label(monday),
                "range": f"{monday:%d.%m} – {monday + timedelta(days=6):%d.%m}",
                "total": total,
                "new": joined.get(monday, 0),
                "active": len(active.get(monday, ())),
            }
        )
    return rows


def _faculties(since):
    """Fakultetlar kesimida: talabalar soni va 30 kunda faol bo'lganlar ulushi."""
    active_ids = _active_since(since)
    names = {f.pk: f for f in Faculty.objects.all()}
    counts, active = {}, {}
    for user_id, faculty_id in _students().filter(faculty__isnull=False).values_list("id", "faculty_id"):
        counts[faculty_id] = counts.get(faculty_id, 0) + 1
        active[faculty_id] = active.get(faculty_id, 0) + (user_id in active_ids)
    top = max(counts.values(), default=0)
    rows = [
        {
            "name": names[pk].short_name or names[pk].name,
            "full": names[pk].name,
            "students": n,
            "rate": round(active[pk] * 100 / n),
            "width": round(n * 100 / top),
        }
        for pk, n in counts.items()
        if pk in names
    ]
    return sorted(rows, key=lambda r: (-r["students"], r["name"]))


def _mix(since):
    labels = dict(PointTransaction.Reason.choices)
    rows = [
        {"reason": row["reason"], "label": labels.get(row["reason"], row["reason"]), "xp": row["xp"] or 0}
        for row in PointTransaction.objects.filter(created_at__gte=since, user__role=User.Role.STUDENT)
        .exclude(reason__in=MIX_EXCLUDE)
        .values("reason")
        .annotate(xp=Sum("xp"))
        .order_by("-xp")
        if row["xp"]
    ]
    total = sum(r["xp"] for r in rows)
    top = max((r["xp"] for r in rows), default=0)
    for row in rows:
        row["share"] = round(row["xp"] * 100 / total) if total else 0
        row["width"] = round(row["xp"] * 100 / top) if top else 0
    return rows


def compute(now=None) -> dict:
    now = now or timezone.now()
    week_ago, two_weeks_ago, month_ago = now - timedelta(days=7), now - timedelta(days=14), now - timedelta(days=30)
    students = _students()
    total = students.count()
    this_week = _active_since(week_ago)
    # Qaytib keluvchilar: o'tgan haftada faol bo'lganlarning shu haftada ham faol bo'lgani
    last_week = _active_ids_between(two_weeks_ago, week_ago)
    retention = round(len(last_week & this_week) * 100 / len(last_week)) if last_week else None

    submissions = Submission.objects.all()
    reviewed = submissions.exclude(status=Submission.Status.PENDING)
    redemptions = Redemption.objects.all()
    return {
        "updated_at": now,
        "students": total,
        "new_week": students.filter(date_joined__gte=week_ago).count(),
        "active_week": len(this_week),
        "active_share": round(len(this_week) * 100 / total) if total else 0,
        "retention": retention,
        "submissions": submissions.count(),
        "reviewed": reviewed.count(),
        "accepted": submissions.filter(status=Submission.Status.ACCEPTED).count(),
        "challenges": Challenge.objects.filter(is_published=True).count(),
        "reviewers": reviewed.filter(reviewed_by__isnull=False).values("reviewed_by").distinct().count(),
        "achievements": Achievement.objects.filter(status=Achievement.Status.APPROVED).count(),
        "endorsements": Endorsement.objects.count(),
        "badges": UserBadge.objects.filter(user__role=User.Role.STUDENT).count(),
        "gifts": redemptions.count(),
        "gifts_delivered": redemptions.filter(status=Redemption.Status.DELIVERED).count(),
        "coins_spent": redemptions.aggregate(n=Sum("price"))["n"] or 0,
        "events": Event.objects.count(),
        "attended": EventRegistration.objects.filter(attended_at__isnull=False).count(),
        "projects": Project.objects.count(),
        "team_members": ProjectMember.objects.filter(status=ProjectMember.Status.ACTIVE).count(),
        "applications": Application.objects.count(),
        "ai_dialogs": Conversation.objects.count(),
        "sponsors": Sponsor.objects.filter(is_active=True).count(),
        "weekly": _weekly(now),
        "faculties": _faculties(month_ago),
        "mix": _mix(month_ago),
    }


def _active_ids_between(start, end) -> set:
    ids = set(
        PointTransaction.objects.filter(created_at__gte=start, created_at__lt=end, user__role=User.Role.STUDENT)
        .exclude(reason__in=MIX_EXCLUDE)
        .values_list("user_id", flat=True)
    )
    ids |= set(Submission.objects.filter(created_at__gte=start, created_at__lt=end).values_list("user_id", flat=True))
    return ids


def impact(institution) -> dict:
    key = f"impact:{institution.pk}"
    data = cache.get(key)
    if data is None:
        data = compute()
        cache.set(key, data, CACHE_SECONDS)
    return data
