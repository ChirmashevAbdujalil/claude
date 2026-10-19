"""So'rovnoma natijasidan klublar: bir xil yo'nalish yoki ko'nikmani tanlagan talabalar bitta jamoaga yig'iladi."""

import csv
import io
from collections import Counter

from django.contrib.auth import get_user_model
from django.db import transaction
from django.urls import reverse
from django.utils import timezone

from apps.notifications.models import Notification
from apps.talent.tracks import ICONS

from . import analytics
from .models import Club, ClubMember, Question
from .services import OTHER, register_talents

User = get_user_model()
Kind = Question.Kind
CLUB_KINDS = Question.CHOICE_KINDS | {Kind.TRACK}
MIN_MEMBERS = 3

KEYWORD_EMOJI = [
    (("python", "dastur", "javascript", "java", "c++", "go", "it ", "kod"), "💻"),
    (("olimpiad", "matemat", "fizika", "kimyo", "biolog"), "🏅"),
    (("ilmiy", "maqola", "tezis", "tadqiqot"), "🔬"),
    (("hakaton", "hackathon"), "⚡"),
    (("startap", "startup", "biznes", "tadbirkor"), "🚀"),
    (("ixtiro", "patent", "muhandis", "robot"), "⚙️"),
    (("dizayn", "ijod", "san'at", "media", "foto", "video"), "🎨"),
    (("sport", "futbol", "shaxmat"), "🏆"),
    (("ingliz", "rus", "nemis", "koreys", "turk", "yapon", "til"), "🌍"),
    (("musiqa", "qo'shiq"), "🎵"),
]


def club_questions(survey):
    return [q for q in survey.questions.all() if q.kind in CLUB_KINDS]


def emoji_for(question, value) -> str:
    if question.kind == Kind.TRACK:
        return ICONS.get(value, "🧭")
    text = f" {value.lower()} "
    for words, emoji in KEYWORD_EMOJI:
        if any(word in text for word in words):
            return emoji
    return "🧩"


def name_for(question, value) -> str:
    label = analytics.label_of(question, value)
    return f"{label} klubi"[:120]


def _matching(question, responses, value):
    key = str(question.pk)
    return [r for r in responses if value in analytics.values_of(question, r.answers.get(key))]


def preview(survey, question, responses) -> list[dict]:
    """Har bir variant bo'yicha nechta talaba klubga tushadi va klub allaqachon bormi."""
    existing = set(Club.objects.filter(survey=survey, question=question).values_list("option", flat=True))
    key = str(question.pk)
    counts = Counter()
    for answers in responses.values_list("answers", flat=True):
        for value in set(analytics.values_of(question, answers.get(key))):
            if value != OTHER:
                counts[value] += 1
    return [
        {
            "value": value,
            "label": label,
            "emoji": emoji_for(question, value),
            "count": counts[value],
            "exists": value in existing,
        }
        for value, label in question.choices
    ]


def _score(questions, response) -> float:
    """Sardorlik uchun taklif: ko'proq savolga javob bergan, o'zini yuqori baholagan va faolroq talaba."""
    score = 0.0
    for q in questions:
        value = response.answers.get(str(q.pk))
        if value in (None, "", []):
            continue
        score += 1
        if q.kind == Kind.SCALE:
            score += int(value) * 2 / max(q.scale_max, 1) * 5
        elif q.kind == Kind.MULTIPLE:
            score += len(value) * 0.5
        elif q.kind == Kind.LONG:
            score += min(len(str(value)) / 100, 3)
    return score


def suggest_leader(club):
    members = [m.response for m in club.members.select_related("response", "response__user") if m.response.user_id]
    if not members or club.question is None:
        return None
    questions = list(club.survey.questions.all())
    best = max(members, key=lambda r: (_score(questions, r), -r.pk))
    return best.user


def _notify(users, club, title, body):
    url = reverse("web:club-page", args=[club.pk])
    Notification.objects.bulk_create(
        [Notification(user_id=pk, title=title[:200], body=body[:500], url=url, icon=club.emoji) for pk in users],
        batch_size=500,
    )


@transaction.atomic
def form_clubs(survey, question, responses, *, by, values=None, min_members=MIN_MEMBERS) -> dict:
    """Tanlangan variantlar bo'yicha klub ochadi (bor bo'lsa, yangi a'zolarni qo'shadi).

    Kamida `min_members` talaba tanlagan variantlardan klub tuziladi. A'zolarga bildirishnoma yuboriladi.
    """
    result = {"created": 0, "updated": 0, "members": 0}
    rows = list(responses.select_related("user"))
    for item in preview(survey, question, responses):
        if values is not None and item["value"] not in values:
            continue
        if item["count"] < min_members and not item["exists"]:
            continue
        club, created = Club.objects.get_or_create(
            survey=survey,
            question=question,
            option=item["value"],
            defaults={"name": name_for(question, item["value"]), "emoji": item["emoji"], "created_by": by},
        )
        added = add_members(club, _matching(question, rows, item["value"]))
        result["created" if created else "updated"] += 1
        result["members"] += len(added)
        if club.leader_id is None:
            club.leader = suggest_leader(club)
            if club.leader:
                club.save(update_fields=["leader", "updated_at"])
        users = [r.user_id for r in added if r.user_id]
        if users:
            body = f"«{survey.title}» so'rovnomasidagi javobingiz asosida. A'zolar va mentor klub sahifasida."
            _notify(users, club, f"Siz «{club.name}»ga qo'shildingiz {club.emoji}", body)
    return result


def add_members(club, responses) -> list:
    have = set(club.members.values_list("response_id", flat=True))
    new = [r for r in responses if r.pk not in have]
    ClubMember.objects.bulk_create([ClubMember(club=club, response=r) for r in new], ignore_conflicts=True)
    return new


def sync(club, responses) -> int:
    """Klub tuzilgandan keyin kelgan javoblarni ham qo'shadi."""
    if club.question is None:
        return 0
    added = add_members(club, _matching(club.question, list(responses.select_related("user")), club.option))
    users = [r.user_id for r in added if r.user_id]
    if users:
        _notify(users, club, f"Siz «{club.name}»ga qo'shildingiz {club.emoji}", "A'zolar va mentor klub sahifasida.")
    return len(added)


def stats(club) -> dict:
    members = [m.response for m in club.members.select_related("response__faculty", "response__user")]
    faculties = Counter(r.faculty.short_name if r.faculty_id else "—" for r in members)
    courses = Counter(r.course for r in members if r.course)
    return {
        "count": len(members),
        "accounts": sum(1 for r in members if r.user_id),
        "faculties": faculties.most_common(4),
        "courses": sorted(courses.items()),
    }


def overview(survey) -> list[dict]:
    clubs = list(survey.clubs.select_related("leader", "mentor", "question"))
    return [{"club": c, **stats(c)} for c in clubs]


def notify_members(club, title, body) -> int:
    users = list(club.members.filter(response__user__isnull=False).values_list("response__user_id", flat=True))
    _notify(users, club, title, body)
    return len(users)


def register_members(club, by) -> dict:
    from .models import Response

    responses = Response.objects.filter(club_memberships__club=club)
    return register_talents(club.survey, responses, by)


def mentors():
    return User.objects.filter(role__in=[User.Role.TEACHER, User.Role.MENTOR, User.Role.DEAN, User.Role.RECTOR],
                               is_active=True).order_by("last_name", "first_name")  # fmt: skip


def is_member(club, user) -> bool:
    return user.is_authenticated and club.members.filter(response__user=user).exists()


def clubs_of(user):
    return Club.objects.filter(members__response__user=user).distinct().select_related("survey", "mentor")


def members_csv(club) -> str:
    out = io.StringIO()
    out.write("﻿")
    writer = csv.writer(out)
    writer.writerow([club.name, f"{timezone.localtime():%d.%m.%Y %H:%M}"])
    writer.writerow(["№", "F.I.Sh.", "Fakultet", "Kurs", "Guruh", "Telefon", "Login", "Rol"])
    for number, member in enumerate(club.members.select_related("response__faculty", "response__user"), 1):
        r = member.response
        role = "Sardor" if r.user_id and r.user_id == club.leader_id else "A'zo"
        writer.writerow([number, r.display_name, getattr(r.faculty, "name", ""), r.course or "", r.group, r.phone,
                         r.user.username if r.user_id else "", role])  # fmt: skip
    return out.getvalue()
