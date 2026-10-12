"""SaaS: OTMlarni ulash, tarif limitlari, platforma statistikasi va OTMlararo liga."""

import secrets
from datetime import timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.db import transaction
from django.db.models import Count, Q, Sum
from django.utils import timezone
from django.utils.text import slugify

from . import plans
from .context import activate, unscoped
from .models import Institution, InstitutionRequest

ADMIN_GROUP = "OTM administratori"
# OTM administratori admin panelda boshqaradigan modellar
ADMIN_MODELS = {
    "opportunities": ["reward", "sponsor", "opportunity", "redemption", "application"],
    "discovery": ["challenge", "submission"],
    "community": ["event"],
    "accounts": ["faculty", "user"],
    "profiles": ["achievement"],
}
RESERVED_SLUGS = {"www", "admin", "api", "platform", "saas", "static", "media", "mail"}


class TenantError(Exception):
    pass


def student_count(institution) -> int:
    User = get_user_model()
    with unscoped():
        return User.objects.filter(
            institution=institution, role=User.Role.STUDENT, is_active=True, is_superuser=False
        ).count()


def registration_state(institution) -> tuple[bool, str]:
    """(ochiqmi, sabab). Sabab: "closed" yoki "limit"."""
    if institution is None or not settings.REGISTRATION_OPEN or not institution.registration_open:
        return False, "closed"
    limit = institution.student_limit
    if limit is not None and student_count(institution) >= limit:
        return False, "limit"
    return True, ""


def unique_slug(text: str) -> str:
    base = slugify(text)[:40].strip("-") or "otm"
    if base in RESERVED_SLUGS:
        base = f"{base}-otm"
    slug, n = base, 2
    while Institution.objects.filter(slug=slug).exists():
        slug, n = f"{base}-{n}", n + 1
    return slug


def ensure_admin_group() -> Group:
    group, _ = Group.objects.get_or_create(name=ADMIN_GROUP)
    perms = Permission.objects.filter(
        Q(
            *[Q(content_type__app_label=app, content_type__model__in=models) for app, models in ADMIN_MODELS.items()],
            _connector=Q.OR,
        )
    )
    group.permissions.set(perms)
    return group


def pilot_until(plan: str, days: int = 90):
    """Pilot tarifi bepul, lekin muddatli: odatda 90 kun."""
    return timezone.localdate() + timedelta(days=days) if plan == "pilot" else None


def check_admin_username(username: str) -> None:
    User = get_user_model()
    with unscoped():
        if User.objects.filter(username=username).exists():
            raise TenantError(f"«{username}» logini band")


def create_admin(institution, username="", contact_name="", contact_email=""):
    """OTM administratori (rektorat roli). Parol bir marta qaytariladi."""
    User = get_user_model()
    username = username or f"{institution.slug}_admin"
    check_admin_username(username)
    password = secrets.token_urlsafe(9)
    with activate(institution):
        admin = User.objects.create_user(
            username=username,
            password=password,
            first_name=contact_name.split(" ")[0] if contact_name else "Administrator",
            email=contact_email,
            role=User.Role.RECTOR,
            is_staff=True,
            onboarded_at=timezone.now(),
        )
    admin.groups.add(ensure_admin_group())
    return admin, password


def reset_password(user) -> str:
    """Yangi tasodifiy parol o'rnatadi va uni qaytaradi (bazada faqat hash saqlanadi)."""
    password = secrets.token_urlsafe(9)
    user.set_password(password)
    user.save(update_fields=["password"])
    return password


def reset_admin_password(institution):
    """OTMning birinchi administratori parolini yangilaydi: (admin, parol) yoki None."""
    User = get_user_model()
    with unscoped():
        admin = (
            User.objects.filter(institution=institution, role=User.Role.RECTOR, is_active=True)
            .order_by("date_joined")
            .first()
        )
    if admin is None:
        return None
    return admin, reset_password(admin)


def staff_accounts() -> dict:
    """OTM id -> rahbariyat va o'qituvchilar hisoblari (platforma paneli uchun)."""
    User = get_user_model()
    result = {}
    with unscoped():
        rows = (
            User.objects.filter(role__in=User.REVIEWER_ROLES, is_superuser=False)
            .select_related("faculty")
            .order_by("institution_id", "role", "username")
        )
        for user in rows:
            result.setdefault(user.institution_id, []).append(user)
    return result


@transaction.atomic
def create_institution(*, name, short_name, slug="", plan="pilot", contact_name="", contact_phone="", contact_email="",
                       admin_username="", pilot_days=90):  # fmt: skip
    """Yangi OTM va uning administratori (rektorat roli). Parol bir marta qaytariladi."""
    if plan not in plans.PLANS:
        raise TenantError("Noma'lum tarif")
    slug = slugify(slug) if slug else unique_slug(short_name or name)
    if slug in RESERVED_SLUGS or Institution.objects.filter(slug=slug).exists():
        raise TenantError(f"«{slug}» manzili band")
    institution = Institution.objects.create(
        name=name,
        short_name=short_name,
        slug=slug,
        plan=plan,
        contact_name=contact_name,
        contact_phone=contact_phone,
        contact_email=contact_email,
        paid_until=pilot_until(plan, pilot_days),
    )
    admin, password = create_admin(institution, admin_username, contact_name, contact_email)
    return institution, admin, password


def approve_request(request_obj: InstitutionRequest):
    if request_obj.status == InstitutionRequest.Status.APPROVED:
        raise TenantError("Ariza allaqachon tasdiqlangan")
    institution, admin, password = create_institution(
        name=request_obj.institution_name,
        short_name=request_obj.short_name,
        plan=request_obj.plan,
        contact_name=request_obj.contact_name,
        contact_phone=request_obj.phone,
        contact_email=request_obj.email,
    )
    request_obj.status = InstitutionRequest.Status.APPROVED
    request_obj.institution = institution
    request_obj.save(update_fields=["status", "institution"])
    return institution, admin, password


def _student_stats(since=None) -> dict:
    """OTM bo'yicha {id: {"students", "total_xp", "active"}}. Har bir ko'rsatkich alohida so'rov bilan
    hisoblanadi: bitta so'rovda JOIN qilinsa, XP yig'indisi tranzaksiyalar soniga ko'payib ketadi."""
    User = get_user_model()
    with unscoped():
        students = User.objects.filter(role=User.Role.STUDENT, is_active=True, is_superuser=False)
        stats = {
            row["institution"]: {"students": row["n"], "total_xp": row["xp"] or 0, "active": 0}
            for row in students.values("institution").annotate(n=Count("id"), xp=Sum("xp"))
        }
        if since is not None:
            active = (
                students.filter(transactions__created_at__gte=since)
                .values("institution")
                .annotate(n=Count("id", distinct=True))
            )
            for row in active:
                stats.setdefault(row["institution"], {"students": 0, "total_xp": 0, "active": 0})["active"] = row["n"]
    return stats


def total_students() -> int:
    return sum(row["students"] for row in _student_stats().values())


def platform_overview() -> dict:
    """Platforma egasi uchun: barcha OTMlar, faollik va oylik tushum (MRR)."""
    stats = _student_stats(since=timezone.now() - timedelta(days=7))
    empty = {"students": 0, "total_xp": 0, "active": 0}
    institutions = []
    staff = staff_accounts()
    from apps.accounts.models import Faculty

    with unscoped():
        faculties = dict(
            Faculty.objects.values("institution_id").annotate(n=Count("id")).values_list("institution_id", "n")
        )
    for inst in Institution.objects.all():
        row = stats.get(inst.pk, empty)
        limit = inst.student_limit
        institutions.append(
            {
                "obj": inst,
                "students": row["students"],
                "active_week": row["active"],
                "total_xp": row["total_xp"],
                "limit": limit,
                "usage": round(row["students"] * 100 / limit) if limit else None,
                "price": inst.plan_info["price"] if inst.is_active else 0,
                "staff": staff.get(inst.pk, []),
                "faculties": faculties.get(inst.pk, 0),
            }
        )
    institutions.sort(key=lambda r: (-r["students"], r["obj"].name))
    return {
        "institutions": institutions,
        "totals": {
            "institutions": len(institutions),
            "active": sum(1 for i in institutions if i["obj"].is_active),
            "students": sum(i["students"] for i in institutions),
            "active_week": sum(i["active_week"] for i in institutions),
            "mrr": sum(i["price"] for i in institutions),
            "requests": InstitutionRequest.objects.filter(status=InstitutionRequest.Status.NEW).count(),
        },
    }


def league() -> list[dict]:
    """OTMlararo liga: o'rtacha XP bo'yicha (katta va kichik OTMlar teng sharoitda)."""
    stats = _student_stats(since=timezone.now() - timedelta(days=30))
    result = []
    for inst in Institution.objects.filter(is_active=True, show_in_league=True):
        row = stats.get(inst.pk)
        if not row or not row["students"] or not inst.has_feature("league"):
            continue
        result.append(
            {
                "obj": inst,
                "students": row["students"],
                "total_xp": row["total_xp"],
                "avg_xp": round(row["total_xp"] / row["students"]),
                "active_share": round(row["active"] * 100 / row["students"]),
            }
        )
    return sorted(result, key=lambda r: (-r["avg_xp"], -r["total_xp"]))
