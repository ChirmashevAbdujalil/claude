"""Iqtidorli talabalar bilan ishlash: reyestr, mentor, rivojlanish rejasi, yo'naltirish va hisobot."""

from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Count, Q
from django.urls import reverse
from django.utils import timezone

from apps.arena.levels import LEVELS
from apps.notifications.services import notify
from apps.profiles.models import Achievement

from .models import DevelopmentGoal, DiagnosticResult, TalentProfile
from .tracks import FROM_OPPORTUNITY, RESULT_KINDS, Track, icon, label

User = get_user_model()

REMIND_BEFORE_DAYS = 3
UNATTENDED_AFTER_DAYS = 14
SUGGESTION_LIMIT = 8


class TalentError(Exception):
    pass


# ---------------------------------------------------------------- huquqlar


def is_management(user) -> bool:
    return user.is_authenticated and user.is_management


def can_view(user, profile: TalentProfile) -> bool:
    if not user.is_authenticated:
        return False
    if profile.student_id == user.pk or profile.mentor_id == user.pk:
        return True
    if user.is_superuser or user.role in {User.Role.RECTOR, User.Role.ADMIN}:
        return True
    return user.role == User.Role.DEAN and (not user.faculty_id or user.faculty_id == profile.student.faculty_id)


def can_manage(user, profile: TalentProfile) -> bool:
    """Mentor biriktirish, yo'nalishni o'zgartirish, arxivlash: rahbariyat."""
    return can_view(user, profile) and is_management(user)


def can_plan(user, profile: TalentProfile) -> bool:
    """Reja tuzish va maqsadlarni baholash: mentor yoki rahbariyat."""
    return profile.mentor_id == user.pk or can_manage(user, profile)


# ---------------------------------------------------------------- reyestr


def registry(viewer, include_archived=False):
    qs = TalentProfile.objects.select_related("student", "student__faculty", "mentor").annotate(
        goals_total=Count("goals", filter=~Q(goals__status=DevelopmentGoal.Status.CANCELLED), distinct=True),
        goals_done=Count("goals", filter=Q(goals__status=DevelopmentGoal.Status.DONE), distinct=True),
        goals_overdue=Count(
            "goals",
            filter=Q(goals__status__in=DevelopmentGoal.OPEN, goals__due_date__lt=timezone.localdate()),
            distinct=True,
        ),
    )
    if not include_archived:
        qs = qs.exclude(status=TalentProfile.Status.ARCHIVED)
    if viewer.is_superuser or viewer.role in {User.Role.RECTOR, User.Role.ADMIN}:
        return qs
    if viewer.role == User.Role.DEAN:
        return qs.filter(student__faculty_id=viewer.faculty_id) if viewer.faculty_id else qs
    return qs.filter(mentor=viewer)


def results(student_ids, start=None, end=None):
    """Natija hisoblanadigan tasdiqlangan yutuqlar: olimpiada, hakaton, maqola, patent."""
    qs = Achievement.objects.filter(
        user_id__in=student_ids, status=Achievement.Status.APPROVED, kind__in=RESULT_KINDS
    ).select_related("user", "user__faculty")
    if start:
        qs = qs.filter(achieved_on__gte=start)
    if end:
        qs = qs.filter(achieved_on__lte=end)
    return qs.order_by("-achieved_on")


def refresh_status(profile: TalentProfile, save: bool = True) -> str:
    if profile.status == TalentProfile.Status.ARCHIVED:
        return profile.status
    if results([profile.student_id]).exists():
        status = TalentProfile.Status.ACHIEVED
    elif profile.goals.exclude(status=DevelopmentGoal.Status.CANCELLED).exists():
        status = TalentProfile.Status.DEVELOPING
    elif profile.mentor_id:
        status = TalentProfile.Status.MENTORED
    else:
        status = TalentProfile.Status.IDENTIFIED
    if status != profile.status:
        profile.status = status
        if save:
            profile.save(update_fields=["status", "updated_at"])
    return status


@transaction.atomic
def ensure_profile(student, *, source, track="", by=None, note=""):
    """Talabani reyestrga qo'shadi (bor bo'lsa, bo'sh maydonlarini to'ldiradi). (profil, yangimi)."""
    if student.role != User.Role.STUDENT:
        raise TalentError("Reyestrga faqat talabalar qo'shiladi")
    profile, created = TalentProfile.objects.get_or_create(
        student=student, defaults={"source": source, "track": track or "", "added_by": by, "note": note}
    )
    changed = []
    if not created:
        if profile.status == TalentProfile.Status.ARCHIVED:
            profile.status = TalentProfile.Status.IDENTIFIED
            changed.append("status")
        if track and not profile.track:
            profile.track = track
            changed.append("track")
        if note and note not in profile.note:
            profile.note = f"{profile.note}\n{note}".strip()
            changed.append("note")
        if changed:
            profile.save(update_fields=[*changed, "updated_at"])
    if not profile.track:
        diagnostic = DiagnosticResult.objects.filter(user=student).first()
        if diagnostic:
            profile.track = diagnostic.track
            profile.save(update_fields=["track", "updated_at"])
    refresh_status(profile)
    if created:
        notify(
            student,
            "Siz iqtidorlar reyestriga kiritildingiz ✨",
            "Rahbariyat sizning salohiyatingizni ko'rdi. Tez orada sizga mentor biriktiriladi.",
            url=reverse("web:my-path"),
            icon="✨",
            kind="success",
        )
    return profile, created


def assign_mentor(profile: TalentProfile, mentor, by=None) -> TalentProfile:
    if mentor is not None and (not mentor.is_active or mentor.role not in User.REVIEWER_ROLES):
        raise TalentError("Mentor sifatida faqat o'qituvchi yoki rahbariyat xodimi tanlanadi")
    if mentor is not None and mentor.institution_id != profile.student.institution_id:
        raise TalentError("Mentor boshqa OTMdan bo'lishi mumkin emas")
    if profile.mentor_id == (mentor.pk if mentor else None):
        return profile
    profile.mentor = mentor
    profile.mentor_assigned_at = timezone.now() if mentor else None
    profile.save(update_fields=["mentor", "mentor_assigned_at", "updated_at"])
    refresh_status(profile)
    if mentor is not None:
        url = reverse("web:talent-profile", args=[profile.pk])
        notify(
            mentor,
            f"Sizga yangi shogird biriktirildi: {profile.student}",
            f"Yo'nalish: {label(profile.track)}. Birinchi navbatda u bilan rivojlanish rejasini tuzing.",
            url=url,
            icon="🧑‍🏫",
        )
        notify(
            profile.student,
            f"Sizga mentor biriktirildi: {mentor}",
            "Mentor bilan uchrashib, semestr uchun rivojlanish rejangizni tuzing.",
            url=reverse("web:my-path"),
            icon="🧑‍🏫",
            kind="success",
        )
    return profile


def suggestions(viewer, limit: int = SUGGESTION_LIMIT) -> list[dict]:
    """Reyestrda yo'q, lekin e'tiborga loyiq talabalar: natijasi bor yoki reytingda yuqori."""
    students = User.objects.filter(role=User.Role.STUDENT, is_active=True, talent_profile__isnull=True)
    if viewer.role == User.Role.DEAN and viewer.faculty_id:
        students = students.filter(faculty_id=viewer.faculty_id)
    found, seen = [], set()
    for achievement in results(students.values("id"))[: limit * 2]:
        if achievement.user_id in seen:
            continue
        seen.add(achievement.user_id)
        found.append(
            {
                "student": achievement.user,
                "reason": f"{achievement.get_kind_display()}: {achievement.title}",
                "source": TalentProfile.Source.ACHIEVEMENT,
                "track": "",
            }  # fmt: skip
        )
    top = students.exclude(pk__in=seen).filter(xp__gt=0).select_related("faculty").order_by("-xp")[:limit]
    for student in top:
        found.append(
            {
                "student": student,
                "reason": f"Reytingda yuqori: {student.xp} XP",
                "source": TalentProfile.Source.RATING,
                "track": "",
            }  # fmt: skip
        )
    diagnostics = dict(
        DiagnosticResult.objects.filter(user__in=[s["student"] for s in found]).values_list("user_id", "track")
    )
    for item in found:
        item["track"] = diagnostics.get(item["student"].pk, "")
    return found[:limit]


def mentors_for(student):
    return User.objects.filter(
        is_active=True, role__in=[User.Role.TEACHER, User.Role.DEAN, User.Role.RECTOR], institution=student.institution
    ).annotate(mentee_count=Count("mentees", filter=~Q(mentees__status=TalentProfile.Status.ARCHIVED)))


# ---------------------------------------------------------------- reja


def save_goal(goal: DevelopmentGoal, by=None) -> DevelopmentGoal:
    if goal.status == DevelopmentGoal.Status.DONE:
        goal.progress = 100
        goal.completed_at = goal.completed_at or timezone.now()
    else:
        goal.completed_at = None
    if goal.pk is None:
        goal.created_by = by
    goal.save()
    refresh_status(goal.profile)
    return goal


# ---------------------------------------------------------------- yo'naltirish


def save_diagnostic(user, answers: dict) -> DiagnosticResult:
    from . import diagnostics

    clean = diagnostics.validate(answers)
    scores, first, second = diagnostics.score(user, clean)
    result, _ = DiagnosticResult.objects.update_or_create(
        user=user, defaults={"answers": clean, "scores": scores, "track": first, "second_track": second}
    )
    profile = TalentProfile.objects.filter(student=user).first()
    if profile and not profile.track:
        profile.track = first
        profile.save(update_fields=["track", "updated_at"])
    return result


def user_tracks(user) -> set:
    tracks = set()
    try:
        profile = user.talent_profile
    except TalentProfile.DoesNotExist:
        profile = None
    if profile and profile.track and profile.status != TalentProfile.Status.ARCHIVED:
        tracks.add(profile.track)
    try:
        tracks.add(user.talent_diagnostic.track)
    except DiagnosticResult.DoesNotExist:
        pass
    return tracks


def opportunity_tracks(opportunity) -> list:
    return list(opportunity.tracks or FROM_OPPORTUNITY.get(opportunity.kind, []))


def matching_students(opportunity):
    tracks = opportunity_tracks(opportunity)
    if not tracks:
        return User.objects.none()
    min_xp = next((xp for number, _, xp in LEVELS if number == opportunity.min_level), 0)
    students = User.objects.filter(role=User.Role.STUDENT, is_active=True, xp__gte=min_xp)
    if opportunity.institution_id:
        students = students.filter(institution_id=opportunity.institution_id)
    in_registry = Q(talent_profile__track__in=tracks) & ~Q(talent_profile__status=TalentProfile.Status.ARCHIVED)
    return students.filter(in_registry | Q(talent_diagnostic__track__in=tracks)).distinct()


def notify_matches(opportunity) -> int:
    """Yangi imkoniyatni iqtidor yo'nalishi mos talabalarga yuboradi (sayt + Telegram)."""
    url = reverse("web:opportunity-detail", args=[opportunity.pk])
    count = 0
    for student in matching_students(opportunity).iterator():
        tracks = user_tracks(student) & set(opportunity_tracks(opportunity))
        reason = label(next(iter(tracks))) if tracks else ""
        notify(
            student,
            f"Sizga mos imkoniyat: {opportunity.title}",
            f"{opportunity.get_kind_display()} · {opportunity.organization}. Yo'nalishingizga mos: {reason}.",
            url=url,
            icon="🎯",
        )
        count += 1
    return count


# ---------------------------------------------------------------- eslatmalar


def send_reminders(today: date | None = None) -> dict:
    """Muddati yaqin va o'tgan maqsadlar, mentorsiz qolgan iqtidorlar haqida eslatmalar (har kuni)."""
    today = today or timezone.localdate()
    stats = {"soon": 0, "overdue": 0, "unattended": 0}
    soon = DevelopmentGoal.objects.filter(
        status__in=DevelopmentGoal.OPEN,
        due_date__gte=today,
        due_date__lte=today + timedelta(days=REMIND_BEFORE_DAYS),
        reminded_on__isnull=True,
    ).select_related("profile__student", "profile__mentor")
    for goal in soon:
        days = (goal.due_date - today).days
        when = "bugun" if days == 0 else f"{days} kundan keyin"
        notify(goal.profile.student, f"Maqsad muddati {when}: {goal.title}", url=reverse("web:my-path"), icon="⏰")
        goal.reminded_on = today
        goal.save(update_fields=["reminded_on"])
        stats["soon"] += 1

    overdue = DevelopmentGoal.objects.filter(
        status__in=DevelopmentGoal.OPEN, due_date__lt=today, overdue_notified=False
    ).select_related("profile__student", "profile__mentor")
    for goal in overdue:
        profile = goal.profile
        notify(profile.student, f"Maqsad muddati o'tdi: {goal.title}", "Mentoringiz bilan yangi muddat kelishing.",
               url=reverse("web:my-path"), icon="⚠️", kind="warning")  # fmt: skip
        if profile.mentor:
            notify(profile.mentor, f"Shogirdingiz maqsadi muddati o'tdi: {profile.student}", goal.title,
                   url=reverse("web:talent-profile", args=[profile.pk]), icon="⚠️", kind="warning")  # fmt: skip
        goal.overdue_notified = True
        goal.save(update_fields=["overdue_notified"])
        stats["overdue"] += 1

    # Mentorsiz qolganlar: haftada bir marta (dushanba) dekan yoki rektoratga
    if today.weekday() == 0:
        limit = timezone.now() - timedelta(days=UNATTENDED_AFTER_DAYS)
        waiting = TalentProfile.objects.filter(
            mentor__isnull=True, created_at__lt=limit, status=TalentProfile.Status.IDENTIFIED
        ).select_related("student")
        by_faculty = {}
        for profile in waiting:
            by_faculty.setdefault((profile.student.institution_id, profile.student.faculty_id), []).append(profile)
        for (institution_id, faculty_id), profiles in by_faculty.items():
            managers = User.objects.filter(institution_id=institution_id, is_active=True, role=User.Role.DEAN,
                                           faculty_id=faculty_id)  # fmt: skip
            if not managers.exists():
                managers = User.objects.filter(institution_id=institution_id, is_active=True, role=User.Role.RECTOR)
            for manager in managers:
                notify(
                    manager,
                    f"{len(profiles)} ta iqtidorli talaba {UNATTENDED_AFTER_DAYS} kundan beri mentorsiz",
                    ", ".join(str(p.student) for p in profiles[:5]),
                    url=reverse("web:talent-registry") + "?mentor=none",
                    icon="🧭",
                    kind="warning",
                )
            stats["unattended"] += len(profiles)
    return stats


# ---------------------------------------------------------------- hisobot


def semester_bounds(today: date | None = None) -> tuple[date, date]:
    """Joriy semestr: kuzgi (1-sentabr - 31-yanvar) yoki bahorgi (1-fevral - 31-avgust)."""
    today = today or timezone.localdate()
    if today.month >= 9:
        return date(today.year, 9, 1), date(today.year + 1, 1, 31)
    if today.month == 1:
        return date(today.year - 1, 9, 1), date(today.year, 1, 31)
    return date(today.year, 2, 1), date(today.year, 8, 31)


def _pct(part, whole):
    return round(part * 100 / whole) if whole else 0


def report(viewer, start: date, end: date) -> dict:
    profiles = list(registry(viewer))
    ids = [p.student_id for p in profiles]
    today = timezone.localdate()
    found_results = list(results(ids, start, end))
    result_students = {r.user_id for r in found_results}
    goals = DevelopmentGoal.objects.filter(profile__in=[p.pk for p in profiles])
    goals_done = goals.filter(status=DevelopmentGoal.Status.DONE, completed_at__date__gte=start,
                              completed_at__date__lte=end).count()  # fmt: skip
    goals_open = goals.filter(status__in=DevelopmentGoal.OPEN)
    total = len(profiles)
    mentored = sum(1 for p in profiles if p.mentor_id)
    planned = sum(1 for p in profiles if p.goals_total)

    def row(name, items):
        n = len(items)
        return {
            "name": name,
            "total": n,
            "mentored": sum(1 for p in items if p.mentor_id),
            "planned": sum(1 for p in items if p.goals_total),
            "achieved": sum(1 for p in items if p.status == TalentProfile.Status.ACHIEVED),
            "results": sum(1 for p in items if p.student_id in result_students),
            "mentored_pct": _pct(sum(1 for p in items if p.mentor_id), n),
        }

    faculties = {}
    for p in profiles:
        faculty = p.student.faculty
        key = (faculty.short_name, faculty.name) if faculty else ("—", "Fakultetsiz")
        faculties.setdefault(key, []).append(p)
    tracks = {}
    for p in profiles:
        tracks.setdefault(p.track or "", []).append(p)

    mentors = {}
    for p in profiles:
        if p.mentor_id:
            m = mentors.setdefault(p.mentor_id, {"name": str(p.mentor), "mentees": 0, "goals": 0, "done": 0,
                                                 "overdue": 0})  # fmt: skip
            m["mentees"] += 1
            m["goals"] += p.goals_total
            m["done"] += p.goals_done
            m["overdue"] += p.goals_overdue

    unattended = sorted((p for p in profiles if not p.mentor_id), key=lambda p: p.created_at)
    return {
        "start": start,
        "end": end,
        "generated_at": timezone.now(),
        "totals": {
            "registry": total,
            "new": sum(1 for p in profiles if start <= timezone.localdate(p.created_at) <= end),
            "mentored": mentored,
            "mentored_pct": _pct(mentored, total),
            "planned": planned,
            "planned_pct": _pct(planned, total),
            "achieved": sum(1 for p in profiles if p.status == TalentProfile.Status.ACHIEVED),
            "results": len(found_results),
            "result_students": len(result_students),
            "goals_done": goals_done,
            "goals_open": goals_open.count(),
            "goals_overdue": goals_open.filter(due_date__lt=today).count(),
            "unattended": len(unattended),
        },
        "by_faculty": sorted(
            ({**row(full, items), "short": short} for (short, full), items in faculties.items()),
            key=lambda r: -r["total"],
        ),
        "by_track": sorted(
            ({**row(f"{icon(t)} {label(t)}", items), "track": t} for t, items in tracks.items()),
            key=lambda r: -r["total"],
        ),
        "by_status": [
            {"status": s, "label": s.label, "count": sum(1 for p in profiles if p.status == s)}
            for s in TalentProfile.PIPELINE
        ],
        "mentors": sorted(mentors.values(), key=lambda m: -m["mentees"]),
        "results": found_results,
        "unattended": unattended,
        "tracks": Track,
    }
