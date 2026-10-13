"""Talabaga yo'l ko'rsatish: «keyingi qadam» tavsiyasi va profil to'liqligi.

Qoidalar muhimlik tartibida tekshiriladi: birinchi mos kelgani asosiy tavsiya bo'ladi.
"""

from dataclasses import dataclass
from datetime import timedelta

from django.urls import reverse
from django.utils import timezone

from apps.arena.models import Streak
from apps.community.models import Event, EventRegistration
from apps.discovery.models import Challenge, Submission
from apps.discovery.selectors import visible_challenges
from apps.profiles.models import Achievement, UserSkill
from apps.projects.models import ProjectMember
from apps.talent.models import DiagnosticResult


@dataclass
class Step:
    icon: str
    title: str
    text: str
    url: str
    action: str
    xp: int = 0


def next_steps(user, limit: int = 3) -> list[Step]:
    steps: list[Step] = []
    today = timezone.localdate()
    now = timezone.now()

    if not user.faculty_id or not user.course:
        steps.append(
            Step(
                "🎓",
                "Profilingizni sozlang",
                "Fakultet va kursingizni tanlang: reyting va challenge'lar shunga qarab moslashadi.",
                reverse("web:welcome"),
                "Sozlash",
            )
        )

    if not UserSkill.objects.filter(user=user).exists():
        steps.append(
            Step(
                "🧬",
                "Ko'nikmalaringizni qo'shing",
                "Ko'nikmalar xaritangiz chiziladi va loyihalarga jamoadosh sifatida tavsiya qilinasiz.",
                reverse("web:profile"),
                "Qo'shish",
            )
        )

    submitted = Submission.objects.filter(user=user).values("challenge_id")
    open_challenges = visible_challenges(user).filter(is_published=True, starts_at__lte=now, ends_at__gte=now)
    open_challenges = open_challenges.exclude(pk__in=submitted).order_by("ends_at")

    streak = Streak.objects.filter(user=user).first()
    daily = open_challenges.filter(kind=Challenge.Kind.DAILY).first()
    if streak and streak.current >= 2 and streak.last_active == today - timedelta(days=1):
        target = daily or open_challenges.first()
        if target:
            steps.append(
                Step(
                    "🔥",
                    f"{streak.current} kunlik streakni saqlab qoling",
                    "Bugun bitta challenge yeching, aks holda streak noldan boshlanadi.",
                    reverse("web:challenge-detail", args=[target.pk]),
                    "Yechish",
                    target.xp_reward,
                )
            )

    if daily:
        steps.append(
            Step(
                "🎯",
                "Bugungi savolni yeching",
                daily.title,
                reverse("web:challenge-detail", args=[daily.pk]),
                "Yechish",
                daily.xp_reward,
            )
        )

    if not DiagnosticResult.objects.filter(user=user).exists():
        steps.append(
            Step(
                "🧭",
                "Iqtidor yo'nalishingizni aniqlang",
                "10 ta savol, 3 daqiqa: sizga mos olimpiada, grant va tanlovlar avtomatik keladi.",
                reverse("web:talent-diagnostic"),
                "Testni boshlash",
            )
        )

    pending_joins = ProjectMember.objects.filter(project__owner=user, status=ProjectMember.Status.PENDING)
    if pending_joins.exists():
        first = pending_joins.select_related("project").first()
        steps.append(
            Step(
                "👋",
                f"{pending_joins.count()} ta jamoaga qo'shilish so'rovi",
                f"«{first.project.title}» loyihangizga qo'shilmoqchi bo'lganlar bor.",
                reverse("web:project-detail", args=[first.project_id]),
                "Ko'rish",
            )
        )

    soon = (
        Event.objects.filter(starts_at__gte=now, starts_at__lte=now + timedelta(days=7))
        .exclude(pk__in=EventRegistration.objects.filter(user=user).values("event_id"))
        .order_by("starts_at")
        .first()
    )
    if soon:
        steps.append(
            Step(
                "📅",
                f"Tadbir: {soon.title}",
                f"{soon.starts_at:%d.%m} · {soon.location}. Ro'yxatdan o'ting va qatnashib XP oling.",
                reverse("web:event-detail", args=[soon.pk]),
                "Ro'yxatdan o'tish",
                soon.xp_reward,
            )
        )

    other = open_challenges.exclude(kind=Challenge.Kind.DAILY).first()
    if other:
        steps.append(
            Step(
                "🧩",
                f"{other.get_kind_display()} challenge",
                other.title,
                reverse("web:challenge-detail", args=[other.pk]),
                "Ko'rish",
                other.xp_reward,
            )
        )

    if not user.portfolio_slug:
        steps.append(
            Step(
                "🔗",
                "Portfolio sahifangizni oching",
                "Bitta havola bilan yutuqlaringizni ish beruvchi va o'qituvchilarga ko'rsating.",
                reverse("web:profile-edit"),
                "Sozlash",
            )
        )

    if not Achievement.objects.filter(user=user).exists():
        steps.append(
            Step(
                "🏅",
                "Yutug'ingizni qo'shing",
                "Olimpiada, sertifikat yoki hakaton: o'qituvchi tasdiqlagach 100–600 XP olasiz.",
                reverse("web:profile-achievement-add"),
                "Qo'shish",
                100,
            )
        )

    steps.append(
        Step(
            "🤖",
            "AI Mentor bilan reja tuzing",
            "Maqsadingizni yozing: shaxsiy o'quv yo'l xaritasini tuzib beradi.",
            reverse("web:ai"),
            "Boshlash",
        )
    )
    unique, seen = [], set()
    for step in steps:
        if step.url not in seen:
            seen.add(step.url)
            unique.append(step)
    return unique[:limit]


def profile_checklist(user) -> dict:
    items = [
        ("Fakultet va kurs", bool(user.faculty_id and user.course), reverse("web:profile-edit")),
        ("O'zingiz haqingizda", bool(user.bio), reverse("web:profile-edit")),
        ("Kamida 3 ta ko'nikma", UserSkill.objects.filter(user=user).count() >= 3, reverse("web:profile")),
        ("Portfolio manzili", bool(user.portfolio_slug), reverse("web:profile-edit")),
        ("Birinchi yutuq", Achievement.objects.filter(user=user).exists(), reverse("web:profile-achievement-add")),
        ("Birinchi challenge", Submission.objects.filter(user=user).exists(), reverse("web:challenges")),
    ]
    done = sum(1 for _, ok, _ in items if ok)
    return {
        "items": [{"label": label, "done": ok, "url": url} for label, ok, url in items],
        "done": done,
        "total": len(items),
        "percent": round(done / len(items) * 100),
    }
