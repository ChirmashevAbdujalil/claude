"""So'rovnomalar: savollar tuzilmasini saqlash, javoblarni tekshirish, yig'ma natija va eksport."""

import csv
import io
import json
import re
from collections import Counter
from datetime import date
from decimal import Decimal, InvalidOperation

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import transaction
from django.db.models import Count, Sum
from django.urls import reverse
from django.utils import timezone

from apps.arena import services as arena
from apps.arena.models import PointTransaction
from apps.notifications.models import Notification
from apps.talent import services as talent_services
from apps.talent.models import TalentProfile
from apps.talent.tracks import Track

from . import files as file_rules
from . import presets
from .models import IssuedAccount, Question, Response, ResponseFile, Survey

User = get_user_model()
Kind = Question.Kind

MAX_QUESTIONS = 100
MAX_OPTIONS = 50
MAX_XP = 200
OTHER = "__other__"
PHONE_RE = re.compile(r"^\+?[\d\s()-]{7,20}$")
# Guruh: 1–5 lotin harf, chiziqcha, ikki raqam, chiziqcha, ikki raqam. Masalan: K-21-05, IBKT-23-01
GROUP_RE = re.compile(r"^[A-Z]{1,5}-\d{2}-\d{2}$")
GROUP_EXAMPLE = "K-21-05"
TEXT_LIMITS = {Kind.SHORT: 500, Kind.LONG: 5000, Kind.EMAIL: 200, Kind.PHONE: 30}


class SurveyError(Exception):
    pass


def normalize_group(value: str) -> str:
    """Talaba qanday yozmasin («k2105», «К 21 05», «k-21/05»), K-21-05 ko'rinishiga keltiradi.

    Keltirib bo'lmasa, katta harfli asl matnni qaytaradi (tekshiruv uni rad etadi).
    """
    from .accounts import latin

    raw = (value or "").strip()
    if not raw:
        return ""
    letters = latin("".join(ch for ch in raw if ch.isalpha())).upper()
    digits = "".join(ch for ch in raw if ch.isdigit())
    if letters and len(digits) == 4:
        return f"{letters}-{digits[:2]}-{digits[2:]}"
    return raw.upper()


# ---------------------------------------------------------------- shablonlar


def _q(kind, title, *, required=False, options=(), help_text="", allow_other=False, **extra):
    return {"kind": kind, "title": title, "required": required, "options": list(options), "help_text": help_text,
            "allow_other": allow_other, **extra}  # fmt: skip


TEMPLATES = {
    "census": {
        "label": "Iqtidorlarni ro'yxatga olish",
        "emoji": "🧭",
        "hint": "Butun institut bo'yicha iqtidorli talabalarni aniqlash uchun tayyor 12 savol",
        "survey": {
            "title": "Iqtidorli talabalarni ro'yxatga olish",
            "description": (
                "Institutimiz har bir iqtidorli talabani bilishi, unga mentor biriktirishi va mos olimpiada, "
                "grant hamda tanlovlarga yo'naltirishi uchun shu qisqa so'rovnomani to'ldiring. 5 daqiqa vaqt oladi."
            ),
            "talent_census": True,
            "xp_reward": 50,
            "thank_you": "Rahmat! Javobingiz iqtidorlar bo'limiga yetib bordi. Siz bilan tez orada bog'lanamiz.",
        },
        "questions": [
            _q(Kind.SECTION, "Qiziqish va yo'nalish"),
            _q(Kind.TRACK, "Qaysi yo'nalishda o'zingizni eng kuchli his qilasiz?", required=True),
            _q(
                Kind.MULTIPLE,
                "Qaysi faoliyatlarda qatnashgansiz?",
                allow_other=True,
                options=[
                    "Fan olimpiadasi",
                    "Ilmiy maqola yoki tezis",
                    "Hakaton yoki IT tanlov",
                    "Startap tanlovi",
                    "Ixtiro yoki patent",
                    "Ijodiy tanlov",
                    "Sport musobaqasi",
                ],
            ),
            _q(
                Kind.SINGLE,
                "Eng yuqori natijangiz qaysi darajada?",
                required=True,
                options=["Hali qatnashmaganman", "OTM ichida", "Viloyat", "Respublika", "Xalqaro"],
            ),
            _q(
                Kind.LONG,
                "Eng katta yutug'ingiz yoki loyihangiz haqida yozing",
                help_text="Qayerda, qachon, qanday natija. Hali bo'lmasa, nima qilmoqchi ekaningizni yozing",
            ),
            _q(Kind.SECTION, "Ko'nikmalar"),
            _q(
                Kind.MULTIPLE,
                "Qaysi chet tillarini bilasiz?",
                allow_other=True,
                options=["Ingliz tili", "Rus tili", "Nemis tili", "Koreys tili", "Turk tili", "Yapon tili"],
            ),
            _q(
                Kind.SINGLE,
                "Til sertifikatingiz bormi?",
                options=["Yo'q", "CEFR B1", "CEFR B2", "CEFR C1 va yuqori", "IELTS 5.5–6.5", "IELTS 7.0 va yuqori"],
            ),
            _q(
                Kind.SCALE,
                "O'z salohiyatingizni qanday baholaysiz?",
                required=True,
                scale_max=5,
                scale_min_label="Boshlang'ich",
                scale_max_label="Juda yuqori",
            ),
            _q(Kind.SHORT, "Portfolio, GitHub yoki ishlaringizga havola"),
            _q(
                Kind.FILE,
                "Yutuqlaringizni tasdiqlovchi hujjatlar (sertifikat, diplom, guvohnoma)",
                help_text="Ixtiyoriy: PDF yoki rasm, 5 tagacha fayl. Hujjatni telefonda suratga olsangiz ham bo'ladi",
                file_types=["pdf", "image"],
                max_files=5,
            ),
            _q(Kind.SECTION, "Rivojlanish"),
            _q(
                Kind.SINGLE,
                "Mentor (ustoz) bilan ishlashni xohlaysizmi?",
                required=True,
                options=["Ha, albatta", "Ha, imkon bo'lsa", "Hozircha yo'q"],
            ),
            _q(Kind.SINGLE, "Haftasiga qancha vaqt ajrata olasiz?", options=["1–3 soat", "4–7 soat", "8 soatdan ko'p"]),
            _q(Kind.LONG, "Institut sizga qanday yordam bersa, yaxshiroq natija ko'rsatasiz?"),
        ],  # fmt: skip
    },
    "feedback": {
        "label": "Tadbir bo'yicha fikr",
        "emoji": "💬",
        "hint": "Tadbir, kurs yoki xakatondan keyin qisqa baholash",
        "survey": {"title": "Tadbir bo'yicha fikringiz", "collect_identity": False, "xp_reward": 10},
        "questions": [
            _q(
                Kind.SCALE,
                "Tadbir sizga qanchalik foydali bo'ldi?",
                required=True,
                scale_max=5,
                scale_min_label="Foydasiz",
                scale_max_label="Juda foydali",
            ),
            _q(
                Kind.MULTIPLE,
                "Nima yoqdi?",
                allow_other=True,
                options=["Mavzu", "Ma'ruzachilar", "Amaliy qism", "Tashkilot", "Networking"],
            ),
            _q(Kind.LONG, "Keyingi safar nimani yaxshilash kerak?"),
        ],  # fmt: skip
    },
    "andti_talent": {
        "label": "«ANDTI TALENT» 1-bosqich",
        "emoji": "🎯",
        "hint": "Talabalar qobiliyatlarini aniqlash: 40 ta qobiliyat, faollik va o'zi haqida 20 savol",
        **presets.ANDTI_TALENT,
    },
    "blank": {
        "label": "Bo'sh so'rovnoma",
        "emoji": "📝",
        "hint": "Savollarni noldan o'zingiz tuzasiz",
        "survey": {"title": "Yangi so'rovnoma"},
        "questions": [_q(Kind.SHORT, "Savol matni")],
    },
}


@transaction.atomic
def create_survey(by, template="blank") -> Survey:
    preset = TEMPLATES.get(template) or TEMPLATES["blank"]
    survey = Survey.objects.create(created_by=by, **preset["survey"])
    save_schema(survey, preset["questions"])
    return survey


@transaction.atomic
def duplicate(survey, by) -> Survey:
    copy = Survey.objects.create(
        title=f"{survey.title} (nusxa)"[:200],
        description=survey.description,
        collect_identity=survey.collect_identity,
        one_response=survey.one_response,
        talent_census=survey.talent_census,
        xp_reward=survey.xp_reward,
        thank_you=survey.thank_you,
        created_by=by,
    )
    save_schema(copy, [{k: v for k, v in item.items() if k != "id"} for item in schema(survey)])
    return copy


# ---------------------------------------------------------------- savollar tuzilmasi


FIELDS = ["kind", "title", "help_text", "required", "options", "allow_other", "scale_max", "scale_min_label",
          "scale_max_label", "file_types", "max_files", "max_file_mb", "to_profile"]  # fmt: skip


def schema(survey) -> list[dict]:
    return [{"id": q.pk, **{f: getattr(q, f) for f in FIELDS}} for q in survey.questions.all()]


def _clean_item(raw, number) -> dict:
    if not isinstance(raw, dict):
        raise SurveyError(f"{number}-savol noto'g'ri")
    kind = raw.get("kind")
    if kind not in Kind.values:
        raise SurveyError(f"{number}-savol: noma'lum tur")
    title = str(raw.get("title") or "").strip()
    if not title:
        raise SurveyError(f"{number}-savol: matnini yozing")
    if len(title) > 300:
        raise SurveyError(f"{number}-savol: matn 300 belgidan oshmasin")
    item = {
        "kind": kind,
        "title": title,
        "help_text": str(raw.get("help_text") or "").strip()[:300],
        "required": bool(raw.get("required")) and kind != Kind.SECTION,
        "options": [],
        "allow_other": False,
        "scale_max": 5,
        "scale_min_label": "",
        "scale_max_label": "",
        "file_types": [],
        "max_files": 1,
        "max_file_mb": file_rules.DEFAULT_FILE_MB,
        "to_profile": False,
    }
    if kind in Question.CHOICE_KINDS:
        options = []
        for option in raw.get("options") or []:
            option = str(option).strip()[:200]
            if option and option not in options:
                options.append(option)
        if not options:
            raise SurveyError(f"{number}-savol: kamida bitta variant kiriting")
        if len(options) > MAX_OPTIONS:
            raise SurveyError(f"{number}-savol: variantlar {MAX_OPTIONS} tadan oshmasin")
        item["options"] = options
        item["allow_other"] = bool(raw.get("allow_other")) and kind != Kind.DROPDOWN
        item["to_profile"] = bool(raw.get("to_profile"))
    if kind == Kind.SCALE:
        try:
            item["scale_max"] = min(max(int(raw.get("scale_max") or 5), 2), 10)
        except (TypeError, ValueError):
            item["scale_max"] = 5
        item["scale_min_label"] = str(raw.get("scale_min_label") or "").strip()[:40]
        item["scale_max_label"] = str(raw.get("scale_max_label") or "").strip()[:40]
    if kind == Kind.FILE:
        types = raw.get("file_types") or []
        item["file_types"] = [t for t in file_rules.TYPES if isinstance(types, list) and t in types]
        item["max_files"] = _bounded(raw.get("max_files"), 1, file_rules.MAX_FILES, 1)
        item["max_file_mb"] = _bounded(raw.get("max_file_mb"), 1, file_rules.MAX_FILE_MB, file_rules.DEFAULT_FILE_MB)
    return item


def _bounded(value, low, high, default) -> int:
    try:
        return min(max(int(value), low), high)
    except (TypeError, ValueError):
        return default


@transaction.atomic
def save_schema(survey, items) -> list[Question]:
    """Konstruktordan kelgan savollar ro'yxatini saqlaydi: mavjudlari yangilanadi, olib tashlanganlari o'chadi.

    Savol identifikatori saqlanadi, shuning uchun eski javoblar o'z savoliga bog'liq qoladi.
    """
    if isinstance(items, str):
        try:
            items = json.loads(items or "[]")
        except ValueError as exc:
            raise SurveyError("Savollar ro'yxatini o'qib bo'lmadi") from exc
    if not isinstance(items, list):
        raise SurveyError("Savollar ro'yxatini o'qib bo'lmadi")
    if len(items) > MAX_QUESTIONS:
        raise SurveyError(f"Savollar {MAX_QUESTIONS} tadan oshmasin")
    cleaned = [
        (raw.get("id") if isinstance(raw, dict) else None, _clean_item(raw, number))
        for number, raw in enumerate(items, 1)
    ]

    existing = {q.pk: q for q in survey.questions.all()}
    was_on = {pk for pk, q in existing.items() if q.to_profile}
    kept, saved = set(), []
    for order, (pk, data) in enumerate(cleaned):
        question = existing.get(pk) if isinstance(pk, int) and pk not in kept else None
        if question is None:
            question = Question(survey=survey)
        for field, value in data.items():
            setattr(question, field, value)
        question.order = order
        question.save()
        kept.add(question.pk)
        saved.append(question)
    survey.questions.exclude(pk__in=kept).delete()
    Survey.objects.filter(pk=survey.pk).update(updated_at=timezone.now())
    if any(q.to_profile and q.pk not in was_on for q in saved):
        from .skills import sync_survey

        transaction.on_commit(lambda: sync_survey(survey))  # oldin kelgan javoblar ham profilga yoziladi
    return saved


# ---------------------------------------------------------------- javoblarni tekshirish


def _clean_value(question, data):
    """(qiymat, xato). Qiymat None bo'lsa, javob berilmagan."""
    name = f"q{question.pk}"
    kind = question.kind
    other_text = (data.get(f"{name}_other") or "").strip()[:300]

    if kind == Kind.MULTIPLE:
        picked = [v for v in data.getlist(name) if v in question.options]
        if question.allow_other and OTHER in data.getlist(name) and other_text:
            picked.append(other_text)
        return (picked or None), None

    raw = (data.get(name) or "").strip()
    if not raw:
        return None, None
    if kind in (Kind.SINGLE, Kind.DROPDOWN):
        if raw == OTHER and question.allow_other:
            return (other_text or None), None
        return (raw, None) if raw in question.options else (None, "Variantlardan birini tanlang")
    if kind == Kind.TRACK:
        return (raw, None) if raw in Track.values else (None, "Variantlardan birini tanlang")
    if kind == Kind.SCALE:
        if raw.isdigit() and 1 <= int(raw) <= question.scale_max:
            return int(raw), None
        return None, f"1 dan {question.scale_max} gacha baho tanlang"
    if kind == Kind.NUMBER:
        try:
            number = Decimal(raw.replace(",", ".").replace(" ", ""))
        except InvalidOperation:
            return None, "Raqam kiriting"
        if not number.is_finite() or abs(number) >= 10**12:
            return None, "Raqam kiriting"
        return format(number.normalize(), "f"), None
    if kind == Kind.DATE:
        try:
            return date.fromisoformat(raw).isoformat(), None
        except ValueError:
            return None, "Sanani to'g'ri kiriting"
    if len(raw) > TEXT_LIMITS.get(kind, 500):
        return None, f"Javob {TEXT_LIMITS.get(kind, 500)} belgidan oshmasin"
    if kind == Kind.EMAIL:
        try:
            validate_email(raw)
        except ValidationError:
            return None, "Elektron pochtani to'g'ri kiriting"
    if kind == Kind.PHONE and not PHONE_RE.match(raw):
        return None, "Telefon raqamini to'g'ri kiriting, masalan +998 90 123 45 67"
    return raw, None


def clean_answers(survey, data, questions=None, files=None) -> tuple[dict, dict]:
    """POST ma'lumotidan javoblarni oladi. (javoblar, xatolar): kalit savol identifikatori.

    «Fayl yuklash» javobi tekshirilgan fayllar ro'yxati (files.Upload) bo'ladi: submit() ularni saqlaydi.
    """
    answers, errors = {}, {}
    for question in questions if questions is not None else survey.questions.all():
        if not question.is_answerable:
            continue
        if question.kind == Kind.FILE:
            value, error = file_rules.clean(question, files.getlist(f"q{question.pk}") if files else [])
        else:
            value, error = _clean_value(question, data)
        if error:
            errors[question.pk] = error
        elif value is None:
            if question.required:
                errors[question.pk] = "Bu savolga javob berish majburiy"
        else:
            answers[str(question.pk)] = value
    return answers, errors


# ---------------------------------------------------------------- javob yuborish


def already_answered(survey, user=None, browser_key="") -> bool:
    if not survey.one_response:
        return False
    if user is not None and user.is_authenticated:
        return Response.objects.filter(survey=survey, user=user).exists()
    return bool(browser_key) and Response.objects.filter(survey=survey, browser_key=browser_key).exists()


@transaction.atomic
def submit(survey, *, answers, identity=None, user=None, browser_key="") -> Response:
    survey = Survey.objects.select_for_update().get(pk=survey.pk)
    user = user if user is not None and user.is_authenticated else None
    if not survey.is_accepting:
        raise SurveyError("So'rovnoma hozir javob qabul qilmayapti")
    if already_answered(survey, user, browser_key):
        raise SurveyError("Siz bu so'rovnomaga javob bergansiz")
    identity = identity or {}
    answers, uploads = file_rules.split(answers)
    response = Response.objects.create(
        survey=survey,
        user=user,
        full_name=identity.get("full_name") or (user.get_full_name() if user else ""),
        faculty=identity.get("faculty") or (user.faculty if user else None),
        course=identity.get("course") or (user.course if user else None),
        group=identity.get("group", ""),
        tutor=identity.get("tutor"),
        phone=identity.get("phone", ""),
        answers=answers,
        browser_key="" if user else browser_key[:32],
    )
    file_rules.attach(response, uploads)
    if user is None and survey.create_accounts and survey.collect_identity:
        from .accounts import provision

        account, _ = provision(response)
        user = account.user if account is not None else None
    elif user is not None and response.tutor_id:
        from .accounts import remember_tutor

        account = IssuedAccount.objects.filter(user=user).first()
        if account is not None:
            remember_tutor(account, response.tutor_id)
    if response.user_id:
        from .skills import sync_response

        sync_response(response)
    if user is not None and user.role == User.Role.STUDENT and survey.xp_reward:
        arena.award(user, PointTransaction.Reason.SURVEY, min(survey.xp_reward, MAX_XP), ref=f"survey:{survey.pk}",
                    note=survey.title[:100])  # fmt: skip
    return response


# ---------------------------------------------------------------- holat


def answerable_count(survey) -> int:
    return survey.questions.exclude(kind=Kind.SECTION).count()


@transaction.atomic
def publish(survey, *, notify_students=False) -> int:
    """So'rovnomani ochadi. Talabalarga xabar yuborilsa, ularning sonini qaytaradi."""
    if not answerable_count(survey):
        raise SurveyError("Kamida bitta savol qo'shing")
    if survey.is_expired:
        raise SurveyError("Muddat o'tib ketgan: avval muddatni uzaytiring")
    survey.status = Survey.Status.OPEN
    survey.published_at = survey.published_at or timezone.now()
    survey.save(update_fields=["status", "published_at", "updated_at"])
    if not notify_students:
        return 0
    answered = Response.objects.filter(survey=survey, user__isnull=False).values_list("user_id", flat=True)
    students = User.objects.filter(role=User.Role.STUDENT, is_active=True).exclude(pk__in=answered)
    url = reverse("web:survey-fill", args=[survey.token])
    body = (survey.description or "Fikringiz biz uchun muhim. Bir necha daqiqa vaqt oladi.")[:300]
    extra = f" Javob uchun +{survey.xp_reward} XP." if survey.xp_reward else ""
    notes = [
        Notification(
            user_id=pk, title=f"Yangi so'rovnoma: {survey.title}"[:200], body=(body + extra)[:500], url=url, icon="📝"
        )  # fmt: skip
        for pk in students.values_list("pk", flat=True)
    ]
    Notification.objects.bulk_create(notes, batch_size=500)
    return len(notes)


def close(survey):
    survey.status = Survey.Status.CLOSED
    survey.save(update_fields=["status", "updated_at"])


# ---------------------------------------------------------------- huquqlar va ro'yxatlar


def can_edit(user, survey) -> bool:
    return user.is_management and (user.is_institution_admin or survey.created_by_id == user.pk)


def responses_for(user, survey):
    """Foydalanuvchi ko'ra oladigan javoblar: dekan boshqalar tuzgan so'rovnomada faqat o'z fakultetini ko'radi."""
    responses = survey.responses.select_related("user", "faculty")
    if user.role == User.Role.DEAN and not user.is_superuser and user.faculty_id and survey.created_by_id != user.pk:
        responses = responses.filter(faculty_id=user.faculty_id)
    return responses


def open_for(user):
    """Foydalanuvchi hali javob bermagan ochiq so'rovnomalar."""
    surveys = Survey.objects.filter(status=Survey.Status.OPEN).exclude(closes_at__lte=timezone.now())
    answered = Response.objects.filter(user=user, survey__one_response=True).values_list("survey_id", flat=True)
    return surveys.exclude(pk__in=answered)


def management_list():
    return (
        Survey.objects.select_related("created_by")
        .annotate(answers=Count("responses"))
        .order_by("status", "-created_at")
    )


# ---------------------------------------------------------------- natijalar


def _label(question, value):
    if question.kind == Kind.TRACK:
        return dict(Track.choices).get(value, str(value))
    if isinstance(value, list):
        return "; ".join(str(v) for v in value)
    return str(value)


def summary(survey, responses) -> dict:
    questions = list(survey.questions.all())
    rows = list(responses.values_list("answers", flat=True))
    total = len(rows)
    blocks = []
    for question in questions:
        if not question.is_answerable:
            blocks.append({"question": question, "section": True})
            continue
        key = str(question.pk)
        values = [row[key] for row in rows if row.get(key) not in (None, "", [])]
        block = {"question": question, "answered": len(values), "skipped": total - len(values)}
        if question.kind in Question.CHOICE_KINDS or question.kind in (Kind.TRACK, Kind.SCALE):
            known = [v for v, _ in question.choices]
            counts, others = Counter(), []
            for value in values:
                for item in value if isinstance(value, list) else [value]:
                    item = str(item)
                    if item in known:
                        counts[item] += 1
                    else:
                        counts[OTHER] += 1
                        others.append(item)
            bars = [{"label": text, "count": counts[v], "value": v} for v, text in question.choices]
            if counts[OTHER]:
                bars.append({"label": "Boshqa", "count": counts[OTHER], "value": OTHER})
            top = max([b["count"] for b in bars] + [1])
            for bar in bars:
                bar["pct"] = round(bar["count"] * 100 / len(values)) if values else 0
                bar["width"] = round(bar["count"] * 100 / top)
            block |= {"bars": bars, "others": others[:20]}
            if question.kind == Kind.SCALE and values:
                block["average"] = round(sum(int(v) for v in values) / len(values), 1)
        elif question.kind == Kind.FILE:
            block["files"] = file_summary(question, responses)
        elif question.kind == Kind.NUMBER:
            numbers = [Decimal(str(v)) for v in values]
            if numbers:
                block |= {"average": round(sum(numbers) / len(numbers), 2), "min": min(numbers),
                          "max": max(numbers)}  # fmt: skip
            block["texts"] = [str(v) for v in values[:30]]
        else:
            block["texts"] = [str(v) for v in values[:30]]
        blocks.append(block)

    faculties = (
        responses.values("faculty__short_name").annotate(n=Count("id")).order_by("-n")
        if survey.collect_identity
        else []
    )
    courses = responses.exclude(course=None).values("course").annotate(n=Count("id")).order_by("course")
    linked = responses.filter(user__isnull=False).count()
    return {
        "total": total,
        "blocks": blocks,
        "faculties": [(f["faculty__short_name"] or "Ko'rsatilmagan", f["n"]) for f in faculties],
        "courses": [(f"{c['course']}-kurs", c["n"]) for c in courses],
        "linked": linked,
        "today": responses.filter(submitted_at__date=timezone.localdate()).count(),
    }


def file_summary(question, responses) -> dict:
    """«Fayl yuklash» savoli: nechta fayl, umumiy hajm, turlar bo'yicha taqsimot va oxirgi yuklanganlar."""
    stored = ResponseFile.objects.filter(question=question, response__in=responses)
    by_type = {row["category"]: row for row in stored.values("category").annotate(n=Count("id"), size=Sum("size"))}
    count = sum(row["n"] for row in by_type.values())
    top = max([row["n"] for row in by_type.values()] + [1])
    bars = [
        {
            "label": f"{meta['icon']} {meta['label']}",
            "count": by_type[key]["n"],
            "size": file_rules.human_size(by_type[key]["size"] or 0),
            "pct": round(by_type[key]["n"] * 100 / count) if count else 0,
            "width": round(by_type[key]["n"] * 100 / top),
        }
        for key, meta in file_rules.TYPES.items()
        if key in by_type
    ]
    total_size = sum(row["size"] or 0 for row in by_type.values())
    return {
        "count": count,
        "size": file_rules.human_size(total_size) if count else "0 KB",
        "bars": bars,
        "recent": list(stored.select_related("response").order_by("-id")[:8]),
    }


def answer_items(survey, response) -> list[dict]:
    """Bitta javobni ko'rish uchun: har bir savol va javobi, turiga qarab ko'rsatish shakli bilan.

    view: section (bo'lim), empty (javob yo'q), chips (variantlar), scale (shkala), track (yo'nalish),
    files (fayllar), text.
    """
    from apps.talent.tracks import ICONS

    items, number = [], 0
    attached = {}
    for stored in response.files.all():
        attached.setdefault(stored.question_id, []).append(stored)
    for question in survey.questions.all():
        if not question.is_answerable:
            items.append({"question": question, "view": "section"})
            continue
        number += 1
        value = response.answers.get(str(question.pk))
        item = {"question": question, "number": number}
        if question.kind == Kind.FILE and attached.get(question.pk):
            item |= {"view": "files", "files": attached[question.pk]}
        elif value in (None, "", []):
            item["view"] = "empty"
        elif question.kind == Kind.TRACK:
            item |= {"view": "track", "text": _label(question, value), "icon": ICONS.get(value, "✨")}
        elif question.kind == Kind.SCALE:
            score = int(value)
            item |= {"view": "scale", "score": score, "max": question.scale_max,
                     "dots": [n <= score for n in range(1, question.scale_max + 1)]}  # fmt: skip
        elif question.kind in Question.CHOICE_KINDS:
            known = set(question.options)
            values = value if isinstance(value, list) else [value]
            item |= {"view": "chips", "chips": [{"text": str(v), "other": str(v) not in known} for v in values]}
        else:
            item |= {"view": "text", "text": str(value), "long": question.kind == Kind.LONG}
        items.append(item)
    return items


def neighbours(responses, response) -> dict:
    """Javoblar ro'yxatidagi o'rni: oldingi va keyingi javob, tartib raqami."""
    ids = list(responses.values_list("pk", flat=True))
    if response.pk not in ids:
        return {"position": 0, "total": len(ids), "prev": None, "next": None}
    index = ids.index(response.pk)
    return {
        "position": index + 1,
        "total": len(ids),
        "prev": ids[index - 1] if index > 0 else None,
        "next": ids[index + 1] if index + 1 < len(ids) else None,
    }


def render_csv(survey, responses) -> str:
    questions = [q for q in survey.questions.all() if q.is_answerable]
    out = io.StringIO()
    out.write("﻿")
    w = csv.writer(out)
    head = ["№", "Yuborilgan vaqt"]
    if survey.collect_identity:
        head += ["F.I.Sh.", "Fakultet", "Kurs", "Guruh", "Telefon"]
    head += ["Platformadagi login", *[q.title for q in questions]]
    w.writerow(head)
    for number, response in enumerate(responses.order_by("submitted_at", "id"), 1):
        row = [number, timezone.localtime(response.submitted_at).strftime("%d.%m.%Y %H:%M")]
        if survey.collect_identity:
            row += [response.display_name, getattr(response.faculty, "name", ""), response.course or "",
                    response.group, response.phone]  # fmt: skip
        row.append(response.user.username if response.user_id else "")
        for question in questions:
            value = response.answers.get(str(question.pk))
            row.append(_label(question, value) if value not in (None, "", []) else "")
        w.writerow(row)
    return out.getvalue()


# ---------------------------------------------------------------- iqtidorlar reyestri


def track_of(survey, response) -> str:
    for question in survey.questions.all():
        if question.kind == Kind.TRACK:
            value = response.answers.get(str(question.pk))
            if value in Track.values:
                return value
    return ""


def register_talents(survey, responses, by) -> dict:
    """Tanlangan javoblar egalarini iqtidorlar reyestriga qo'shadi."""
    result = {"added": 0, "existing": 0, "skipped": 0}
    for response in responses.select_related("user"):
        student = response.user
        if student is None or student.role != User.Role.STUDENT:
            result["skipped"] += 1
            continue
        _, created = talent_services.ensure_profile(
            student,
            source=TalentProfile.Source.SURVEY,
            track=track_of(survey, response),
            by=by,
            note=f"«{survey.title}» so'rovnomasi orqali aniqlandi"[:300],
        )
        result["added" if created else "existing"] += 1
    return result


def in_registry(responses) -> set[int]:
    ids = [r.user_id for r in responses if r.user_id]
    return set(TalentProfile.objects.filter(student_id__in=ids).values_list("student_id", flat=True))
