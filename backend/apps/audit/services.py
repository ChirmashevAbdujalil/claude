"""Jurnalga yozish va zanjir yaxlitligini tekshirish."""

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.tenants.context import current

from .context import current_request, current_source
from .models import AuditLog

STAFF_ROLES = {"teacher", "dean", "rector", "admin"}


def actor_info():
    """(foydalanuvchi, kim, rol) yoki None: talaba va mehmon harakatlari jurnalga yozilmaydi."""
    request = current_request()
    user = getattr(request, "user", None)
    if user is not None and user.is_authenticated and (user.is_superuser or user.role in STAFF_ROLES):
        role = "Platforma egasi" if user.is_superuser else user.get_role_display()
        return user, user.username, role
    name = current_source()
    if name:
        return None, name, "Tizim"
    return None


def _client(request):
    if request is None:
        return None, ""
    ip = request.META.get("REMOTE_ADDR") or None
    if getattr(settings, "AUDIT_TRUST_X_FORWARDED_FOR", False) and request.META.get("HTTP_X_FORWARDED_FOR"):
        ip = request.META["HTTP_X_FORWARDED_FOR"].split(",")[0].strip() or ip
    return ip, request.META.get("HTTP_USER_AGENT", "")[:255]


@transaction.atomic
def record(action, *, institution_id=None, actor=None, actor_repr="", actor_role="", target=None, changes=None):
    request = current_request()
    if institution_id is None:
        inst = getattr(request, "institution", None) or current()
        institution_id = inst.pk if inst is not None else None
    ip, agent = _client(request)
    last = (
        AuditLog._base_manager.select_for_update()
        .filter(institution_id=institution_id)
        .order_by("-id")
        .values_list("hash", flat=True)
        .first()
    )
    entry = AuditLog(
        institution_id=institution_id,
        actor=actor,
        actor_repr=actor_repr[:150],
        actor_role=actor_role[:40],
        action=action,
        changes=changes or {},
        ip=ip,
        user_agent=agent,
        created_at=timezone.now(),
        prev_hash=last or "",
    )
    if target is not None:
        entry.target_type = target._meta.label_lower
        entry.target_label = str(target._meta.verbose_name)[:100]
        entry.target_id = str(target.pk or "")
        entry.target_repr = str(target)[:255]
    entry.hash = entry.compute_hash()
    entry.save()
    return entry


def verify(institution_id=None, *, all_institutions=False):
    """Zanjirni tekshiradi: (yozuvlar soni, buzilgan birinchi yozuv id yoki None)."""
    qs = AuditLog._base_manager.order_by("institution_id", "id")
    if not all_institutions:
        qs = qs.filter(institution_id=institution_id)
    previous, checked = {}, 0
    for entry in qs.iterator():
        expected_prev = previous.get(entry.institution_id, "")
        if entry.prev_hash != expected_prev or entry.compute_hash() != entry.hash:
            return checked, entry.pk
        previous[entry.institution_id] = entry.hash
        checked += 1
    return checked, None
