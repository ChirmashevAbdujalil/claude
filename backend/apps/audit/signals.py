"""Muhim modellardagi o'zgarishlarni va kirish-chiqishlarni jurnalga yozadi.

Faqat xodimlar (o'qituvchi, dekan, rektorat, administrator) va tizim manbalari (Payme, Click,
obuna nazorati) yoziladi. Talabalarning kundalik harakatlari jurnalni to'ldirib yubormasligi uchun yozilmaydi.
"""

from django.apps import apps
from django.contrib.auth.signals import user_logged_in, user_logged_out, user_login_failed
from django.db.models.signals import post_delete, post_save, pre_save

from . import services
from .models import AuditLog

# model -> sozlama: fields (faqat shu maydonlar), create (yaratilishi yoziladimi), when (qo'shimcha shart)
TRACKED = {
    "tenants.institution": {},
    "tenants.institutionrequest": {"fields": ["status"], "create": False},
    "accounts.faculty": {},
    "accounts.user": {
        "fields": [
            "username",
            "first_name",
            "last_name",
            "email",
            "role",
            "faculty",
            "course",
            "is_active",
            "is_staff",
            "is_superuser",
            "institution",
            "password",
        ],
    },  # fmt: skip
    "discovery.challenge": {},
    "discovery.submission": {"fields": ["status", "score", "feedback", "xp_awarded"], "create": False},
    "discovery.talentflag": {},
    "profiles.achievement": {"fields": ["status", "xp_awarded"], "create": False},
    "community.event": {},
    "opportunities.opportunity": {},
    "surveys.survey": {"fields": ["title", "status", "access", "talent_census", "xp_reward", "closes_at"]},
    "opportunities.application": {"fields": ["status"], "create": False},
    "opportunities.reward": {},
    "opportunities.sponsor": {},
    "opportunities.redemption": {"fields": ["status"], "create": False},
    "arena.pointtransaction": {"when": lambda obj: obj.reason == "manual"},
    "billing.invoice": {},
    "talent.talentprofile": {"fields": ["student", "track", "status", "mentor", "note"]},
    "talent.developmentgoal": {"fields": ["title", "kind", "due_date", "status", "progress", "mentor_comment"]},
}
SKIP_FIELDS = {"id", "last_login", "date_joined", "created_at", "updated_at", "ai_suggestion", "ai_uses_date"}
SECRET_FIELDS = {"password"}
MAX_VALUE = 300


def _fields(model, config):
    names = config.get("fields")
    result = []
    for field in model._meta.concrete_fields:
        if names is not None and field.name not in names:
            continue
        if names is None and (field.name in SKIP_FIELDS or getattr(field, "auto_now", False)):
            continue
        result.append(field)
    return result


def _display(instance, field):
    if field.name in SECRET_FIELDS:
        return "••••••"
    if field.is_relation:
        related = getattr(instance, field.name, None)
        return str(related) if related is not None else "—"
    value = field.value_from_object(instance)
    if field.choices:
        return str(dict(field.flatchoices).get(value, value))
    if isinstance(value, bool):
        return "ha" if value else "yo'q"
    if value in (None, ""):
        return "—"
    if hasattr(value, "name") and hasattr(value, "url"):  # fayl
        return value.name or "—"
    text = str(value)
    return text if len(text) <= MAX_VALUE else text[: MAX_VALUE - 1] + "…"


def _institution_id(instance):
    if instance._meta.label_lower == "tenants.institution":
        return instance.pk
    if hasattr(instance, "institution_id"):
        return instance.institution_id
    path = getattr(type(instance), "tenant_path", "")
    obj = instance
    parts = path.split("__") if path else []
    for part in parts[:-1]:
        obj = getattr(obj, part, None)
        if obj is None:
            return None
    return getattr(obj, f"{parts[-1]}_id", None) if parts else None


def _config(instance):
    config = TRACKED.get(instance._meta.label_lower)
    if config is None:
        return None
    when = config.get("when")
    if when is not None and not when(instance):
        return None
    return config


def _before_save(sender, instance, raw=False, **kwargs):
    if raw or instance.pk is None or _config(instance) is None:
        return
    instance._audit_old = sender._base_manager.filter(pk=instance.pk).first()


def _after_save(sender, instance, created, raw=False, **kwargs):
    config = _config(instance)
    if raw or config is None:
        return
    actor = services.actor_info()
    if actor is None:
        return
    fields = _fields(sender, config)
    old = getattr(instance, "_audit_old", None)
    instance._audit_old = None
    if created or old is None:
        if not config.get("create", True):
            return
        changes = {
            f.name: {"label": str(f.verbose_name), "new": _display(instance, f)}
            for f in fields
            if f.name not in SECRET_FIELDS and _display(instance, f) != "—"
        }
        action = AuditLog.Action.CREATE
    else:
        changes = {
            f.name: {"label": str(f.verbose_name), "old": _display(old, f), "new": _display(instance, f)}
            for f in fields
            if f.value_from_object(old) != f.value_from_object(instance)
        }
        if not changes:
            return
        action = AuditLog.Action.PASSWORD if set(changes) == {"password"} else AuditLog.Action.UPDATE
    user, name, role = actor
    services.record(
        action,
        institution_id=_institution_id(instance),
        actor=user,
        actor_repr=name,
        actor_role=role,
        target=instance,
        changes=changes,
    )


def _after_delete(sender, instance, **kwargs):
    config = _config(instance)
    if config is None:
        return
    actor = services.actor_info()
    if actor is None:
        return
    user, name, role = actor
    changes = {
        f.name: {"label": str(f.verbose_name), "old": _display(instance, f)}
        for f in _fields(sender, config)
        if f.name not in SECRET_FIELDS
    }
    services.record(
        AuditLog.Action.DELETE,
        institution_id=_institution_id(instance),
        actor=user,
        actor_repr=name,
        actor_role=role,
        target=instance,
        changes=changes,
    )


def _is_staff(user):
    return user is not None and (user.is_superuser or getattr(user, "role", "") in services.STAFF_ROLES)


def _logged_in(sender, request, user, **kwargs):
    if _is_staff(user):
        role = "Platforma egasi" if user.is_superuser else user.get_role_display()
        services.record(
            AuditLog.Action.LOGIN,
            institution_id=user.institution_id,
            actor=user,
            actor_repr=user.username,
            actor_role=role,
        )


def _logged_out(sender, request, user, **kwargs):
    if _is_staff(user):
        role = "Platforma egasi" if user.is_superuser else user.get_role_display()
        services.record(
            AuditLog.Action.LOGOUT,
            institution_id=user.institution_id,
            actor=user,
            actor_repr=user.username,
            actor_role=role,
        )


def _login_failed(sender, credentials, request=None, **kwargs):
    # Parolni taxmin qilish urinishlarini ko'rish uchun: login yoziladi, parol hech qachon yozilmaydi
    username = str(credentials.get("username") or "")[:150] or "noma'lum"
    services.record(AuditLog.Action.LOGIN_FAILED, actor_repr=username)


def connect():
    for label in TRACKED:
        model = apps.get_model(label)
        uid = f"audit:{label}"
        pre_save.connect(_before_save, sender=model, dispatch_uid=uid + ":pre")
        post_save.connect(_after_save, sender=model, dispatch_uid=uid + ":post")
        post_delete.connect(_after_delete, sender=model, dispatch_uid=uid + ":delete")
    user_logged_in.connect(_logged_in, dispatch_uid="audit:login")
    user_logged_out.connect(_logged_out, dispatch_uid="audit:logout")
    user_login_failed.connect(_login_failed, dispatch_uid="audit:login_failed")
