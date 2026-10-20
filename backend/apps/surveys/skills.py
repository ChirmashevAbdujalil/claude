"""So'rovnomadagi qobiliyat javoblarini talaba profiliga ko'nikma sifatida yozish.

«Profilga qobiliyat bo'lib yoziladi» belgilangan savolda talaba tanlagan har bir variant (masalan, «🎬 Video
montaj») profildagi ko'nikmaga aylanadi. Shu tufayli so'rovnoma oddiy jadval emas, iqtidorlar qidiruvi
ishlaydigan jonli bazaga aylanadi.
"""

import re

from apps.profiles.models import Skill, UserSkill

from .models import Question, Response

SURVEY_LEVEL = 2  # so'rovnomadan kelgan ko'nikma: talaba o'zi belgilagan, hali tasdiqlanmagan
LEADING_SYMBOLS = re.compile(r"^[^\w«\"(]+")

CATEGORY_WORDS = {
    Skill.Category.PROGRAMMING: ("dastur", "web", "mobil", "sun'iy", "intellekt", "excel", "ma'lumot", "kiber"),
    Skill.Category.DESIGN: ("dizayn", "video", "foto", "grafik", "montaj"),
    Skill.Category.ENGINEERING: ("mexanika", "elektron", "texnika", "avtomobil", "qurilish", "chizma", "robot"),
    Skill.Category.RESEARCH: ("ilmiy", "tadqiqot", "zakovat", "maqola"),
    Skill.Category.LEADERSHIP: ("lider", "jamoa", "notiq", "boshlov", "biznes", "startap", "tadbirkor", "dars"),
    Skill.Category.LANGUAGES: ("til",),
}


def skill_name(option: str) -> str:
    """«💻 Dasturlash» → «Dasturlash»: boshidagi emoji va belgilar olib tashlanadi."""
    return LEADING_SYMBOLS.sub("", str(option)).strip()[:100]


def category_of(name: str) -> str:
    lower = name.lower()
    for category, words in CATEGORY_WORDS.items():
        if any(word in lower for word in words):
            return category
    return Skill.Category.OTHER


def skill_for(option: str, cache: dict) -> Skill | None:
    name = skill_name(option)
    if not name:
        return None
    key = name.lower()
    if key not in cache:
        skill = Skill.objects.filter(name__iexact=name).first()
        if skill is None:
            skill = Skill.objects.create(name=name, category=category_of(name))
        cache[key] = skill
    return cache[key]


def _picked(question, raw) -> list[str]:
    """Faqat ro'yxatdagi variantlar: «Boshqa» ga yozilgan erkin matn profilga o'tmaydi."""
    if raw in (None, "", []):
        return []
    known = set(question.options)
    return [str(v) for v in (raw if isinstance(raw, list) else [raw]) if str(v) in known]


def sync_response(response, questions=None, cache=None) -> int:
    """Bitta javobdagi qobiliyatlarni profilga yozadi. Yangi qo'shilgan ko'nikmalar soni."""
    if not response.user_id:
        return 0
    if questions is None:
        questions = [q for q in response.survey.questions.all() if q.to_profile and q.kind in Question.CHOICE_KINDS]
    cache = {} if cache is None else cache
    added = 0
    have = set(UserSkill.objects.filter(user_id=response.user_id).values_list("skill_id", flat=True))
    for question in questions:
        for option in _picked(question, response.answers.get(str(question.pk))):
            skill = skill_for(option, cache)
            if skill is None or skill.pk in have:
                continue
            UserSkill.objects.create(user_id=response.user_id, skill=skill, level=SURVEY_LEVEL)
            have.add(skill.pk)
            added += 1
    return added


def sync_survey(survey) -> int:
    questions = [q for q in survey.questions.all() if q.to_profile and q.kind in Question.CHOICE_KINDS]
    if not questions:
        return 0
    cache, added = {}, 0
    for response in Response.objects.filter(survey=survey, user__isnull=False).select_related("survey"):
        added += sync_response(response, questions, cache)
    return added


def sync_all() -> int:
    from .models import Survey

    surveys = Survey.objects.filter(questions__to_profile=True).distinct()
    return sum(sync_survey(survey) for survey in surveys)


# ---------------------------------------------------------------- iqtidorlar qidiruvi


def students_for(viewer):
    """Qidiruvda ko'rinadigan talabalar: dekan faqat o'z fakultetini ko'radi."""
    from django.contrib.auth import get_user_model

    User = get_user_model()
    students = User.objects.filter(role=User.Role.STUDENT, is_active=True)
    if viewer.role == User.Role.DEAN and not viewer.is_superuser and viewer.faculty_id:
        students = students.filter(faculty_id=viewer.faculty_id)
    return students


def popular(students, limit=60) -> list[dict]:
    """Eng ko'p uchraydigan qobiliyatlar va ularga ega talabalar soni."""
    from django.db.models import Count

    rows = (
        UserSkill.objects.filter(user__in=students)
        .values("skill_id", "skill__name", "skill__category")
        .annotate(n=Count("user_id", distinct=True))
        .order_by("-n", "skill__name")[:limit]
    )
    return [
        {"id": r["skill_id"], "name": r["skill__name"], "category": r["skill__category"], "count": r["n"]} for r in rows
    ]


def search(viewer, params):
    """(talabalar, tanlangan ko'nikmalar). params: skill (bir nechta), mode (all|any), faculty, course, group,
    tutor, q."""
    from django.db.models import Count, Q

    students = students_for(viewer)
    ids = [int(v) for v in params.getlist("skill") if str(v).isdigit()]
    chosen = list(Skill.objects.filter(pk__in=ids).order_by("name"))
    if chosen:
        if params.get("mode") == "any":
            students = students.filter(skills__skill__in=chosen)
        else:
            for skill in chosen:
                students = students.filter(skills__skill=skill)
    else:
        students = students.filter(skills__isnull=False)
    if str(params.get("faculty", "")).isdigit():
        students = students.filter(faculty_id=params["faculty"])
    if str(params.get("course", "")).isdigit():
        students = students.filter(course=params["course"])
    if params.get("group"):
        group = params["group"].strip()
        students = students.filter(Q(issued_account__group__iexact=group) | Q(survey_responses__group__iexact=group))
    if str(params.get("tutor", "")).isdigit():
        tutor = params["tutor"]
        students = students.filter(Q(issued_account__tutor_id=tutor) | Q(survey_responses__tutor_id=tutor))
    if params.get("q"):
        q = params["q"].strip()
        students = students.filter(Q(first_name__icontains=q) | Q(last_name__icontains=q) | Q(username__icontains=q))
    students = (
        students.distinct()
        .annotate(skill_count=Count("skills", distinct=True))
        .order_by("faculty__name", "course", "last_name", "first_name")
    )
    return students, chosen


def describe(students, chosen=()) -> list[dict]:
    """Natija kartochkalari uchun: guruh, tyutor, telefon, so'nggi javob va ko'nikmalar."""
    students = list(
        students.select_related(
            "faculty", "issued_account", "issued_account__tutor", "talent_profile"
        ).prefetch_related("skills__skill")
    )
    latest = {}
    for response in (
        Response.objects.filter(user__in=students).select_related("tutor").order_by("user_id", "-submitted_at")
    ):
        latest.setdefault(response.user_id, response)
    chosen_ids = {s.pk for s in chosen}
    cards = []
    for student in students:
        account = getattr(student, "issued_account", None)
        response = latest.get(student.pk)
        tutor = (account.tutor if account and account.tutor_id else None) or (response.tutor if response else None)
        skills = sorted(student.skills.all(), key=lambda us: (us.skill_id not in chosen_ids, -us.level, us.skill.name))
        cards.append(
            {
                "user": student,
                "group": (account.group if account else "") or (response.group if response else ""),
                "phone": (account.phone if account else "") or (response.phone if response else ""),
                "tutor": tutor,
                "response": response,
                "talent": getattr(student, "talent_profile", None),
                "skills": [{"name": us.skill.name, "matched": us.skill_id in chosen_ids} for us in skills],
            }
        )
    return cards
