"""So'rovnoma javobidan talaba akkauntini ochish, boshlang'ich parollar va ularni tarqatish ro'yxati."""

import re
import secrets

from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone

from apps.tenants import services as tenant_services
from apps.tenants.context import current, unscoped

from .models import IssuedAccount, Response

User = get_user_model()

# Parolda adashtiradigan belgilar yo'q: 0/o, 1/l/i
PASSWORD_LETTERS = "abcdefghjkmnpqrstuvwxyz"
PASSWORD_DIGITS = "23456789"

CYRILLIC = {
    "а": "a", "б": "b", "в": "v", "г": "g", "ғ": "g", "д": "d", "е": "e", "ё": "yo", "ж": "j", "з": "z", "и": "i",
    "й": "y", "к": "k", "қ": "q", "л": "l", "м": "m", "н": "n", "о": "o", "ў": "o", "п": "p", "р": "r", "с": "s",
    "т": "t", "у": "u", "ф": "f", "х": "x", "ҳ": "h", "ц": "ts", "ч": "ch", "ш": "sh", "щ": "sh", "ъ": "", "ь": "",
    "ы": "i", "э": "e", "ю": "yu", "я": "ya",
}  # fmt: skip


class AccountError(Exception):
    pass


def new_password() -> str:
    """O'qish va yozish oson, masalan: kmr7-4tqx."""
    pick = secrets.choice
    return (
        "".join(pick(PASSWORD_LETTERS) for _ in range(3))
        + pick(PASSWORD_DIGITS)
        + "-"
        + pick(PASSWORD_DIGITS)
        + "".join(pick(PASSWORD_LETTERS) for _ in range(3))
    )


def latin(text: str) -> str:
    text = "".join(CYRILLIC.get(ch, ch) for ch in text.lower())
    text = re.sub(r"[ʻʼ'`‘’]", "", text)
    return re.sub(r"[^a-z0-9]+", "", text)


def split_name(full_name: str) -> tuple[str, str]:
    """«Familiya Ism Sharif» → (ism, familiya). Sharif saqlanmaydi."""
    parts = [p for p in full_name.split() if p]
    if not parts:
        return "", ""
    if len(parts) == 1:
        return parts[0].title()[:150], ""
    return parts[1].title()[:150], parts[0].title()[:150]


def unique_username(first: str, last: str) -> str:
    base = ".".join(filter(None, [latin(first), latin(last)]))[:24] or "talaba"
    with unscoped():
        taken = set(User.objects.filter(username__startswith=base).values_list("username", flat=True))
    if base not in taken:
        return base
    number = 2
    while f"{base}{number}" in taken:
        number += 1
    return f"{base}{number}"


def normalize_phone(phone: str) -> str:
    digits = re.sub(r"\D", "", phone or "")
    return digits[-9:] if len(digits) >= 9 else digits


def _limit_reached() -> bool:
    institution = current()
    if institution is None or institution.student_limit is None:
        return False
    return tenant_services.student_count(institution) >= institution.student_limit


def _find_existing(first, last, faculty, course, phone):
    """Shu talaba oldin boshqa so'rovnoma orqali akkaunt olgan bo'lsa, o'shani qaytaradi."""
    issued = IssuedAccount.objects.select_related("user")
    if phone:
        account = issued.filter(phone_key=phone).first()
        if account is not None:
            return account
    if first and last and faculty is not None:
        return issued.filter(
            user__first_name__iexact=first, user__last_name__iexact=last, user__faculty=faculty, user__course=course
        ).first()
    return None


@transaction.atomic
def provision(response) -> tuple[IssuedAccount | None, bool]:
    """Akkauntsiz javob uchun talaba akkauntini ochadi (yoki oldingisini topadi) va javobni unga bog'laydi.

    (akkaunt, yangi ochildimi). Ism yo'q yoki talabalar limiti tugagan bo'lsa (None, False).
    """
    if response.user_id or not response.full_name.strip():
        return None, False
    first, last = split_name(response.full_name)
    phone = normalize_phone(response.phone)
    account = _find_existing(first, last, response.faculty, response.course, phone)
    created = False
    if account is None:
        if _limit_reached():
            return None, False
        password = new_password()
        user = User.objects.create_user(
            username=unique_username(first, last),
            password=password,
            first_name=first,
            last_name=last,
            role=User.Role.STUDENT,
            faculty=response.faculty,
            course=response.course,
        )
        account = IssuedAccount.objects.create(
            user=user,
            survey=response.survey,
            initial_password=password,
            group=response.group,
            tutor_id=response.tutor_id,
            phone=response.phone,
            phone_key=phone,
        )
        created = True
    else:
        remember_tutor(account, response.tutor_id)
    Response.objects.filter(pk=response.pk).update(user=account.user)
    response.user = account.user
    return account, created


def remember_tutor(account, tutor_id) -> None:
    """Talaba so'nggi javobida ko'rsatgan tyutor login-parollar ro'yxatida ham ko'rinadi."""
    if tutor_id and account.tutor_id != tutor_id:
        account.tutor_id = tutor_id
        account.save(update_fields=["tutor"])


def provision_survey(survey) -> dict:
    """So'rovnomaning akkauntsiz barcha javoblari uchun akkaunt ochadi."""
    result = {"created": 0, "linked": 0, "skipped": 0}
    for response in survey.responses.filter(user__isnull=True).select_related("faculty").order_by("submitted_at"):
        account, created = provision(response)
        if account is None:
            result["skipped"] += 1
        else:
            result["created" if created else "linked"] += 1
    return result


@transaction.atomic
def reset_password(account) -> str:
    """Yangi boshlang'ich parol: talaba parolini unutsa yoki varaqni yo'qotsa."""
    password = new_password()
    account.user.set_password(password)
    account.user.save(update_fields=["password"])
    account.initial_password = password
    account.must_change_password = True
    account.save(update_fields=["initial_password", "must_change_password"])
    return password


def on_login(user) -> bool:
    """Birinchi kirishda boshlang'ich parol o'chiriladi. Parolni almashtirish kerakmi, qaytaradi."""
    account = IssuedAccount.objects.filter(user=user).first()
    if account is None:
        return False
    changed = []
    if account.initial_password:
        account.initial_password = ""
        changed.append("initial_password")
    if account.first_login_at is None:
        account.first_login_at = timezone.now()
        changed.append("first_login_at")
    if changed:
        account.save(update_fields=changed)
    return account.must_change_password


def password_changed(user) -> None:
    IssuedAccount.objects.filter(user=user).update(must_change_password=False, initial_password="")


def visible_to(user):
    """Rahbariyat ko'radigan akkauntlar: dekan faqat o'z fakultetini."""
    accounts = IssuedAccount.objects.select_related("user", "user__faculty", "survey", "tutor")
    if user.role == User.Role.DEAN and not user.is_superuser and user.faculty_id:
        accounts = accounts.filter(user__faculty_id=user.faculty_id)
    return accounts


def pending_surveys():
    """Akkauntsiz, lekin ismi yozilgan javoblari bor so'rovnomalar: (so'rovnoma, javoblar soni)."""
    from django.db.models import Count, Q

    from .models import Survey

    surveys = (
        Survey.objects.filter(collect_identity=True)
        .annotate(n=Count("responses", filter=Q(responses__user__isnull=True) & ~Q(responses__full_name="")))
        .filter(n__gt=0)
        .order_by("-created_at")
    )
    return [(s, s.n) for s in surveys]
