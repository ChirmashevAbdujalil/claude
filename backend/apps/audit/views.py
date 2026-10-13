import csv
from datetime import datetime, time

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.http import HttpResponse
from django.shortcuts import render
from django.utils import timezone

from . import services
from .models import AuditLog
from .signals import TRACKED


def _filtered(request):
    qs = AuditLog.objects.select_related("actor")
    params = request.GET
    if params.get("action") in AuditLog.Action.values:
        qs = qs.filter(action=params["action"])
    if params.get("type") in TRACKED:
        qs = qs.filter(target_type=params["type"])
    if params.get("q"):
        qs = qs.filter(actor_repr__icontains=params["q"].strip())
    for key, lookup, edge in (("from", "created_at__gte", time.min), ("to", "created_at__lte", time.max)):
        try:
            day = datetime.strptime(params.get(key, ""), "%Y-%m-%d").date()
        except ValueError:
            continue
        qs = qs.filter(**{lookup: timezone.make_aware(datetime.combine(day, edge))})
    return qs


def _csv(entries, institution):
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    stamp = timezone.localtime().strftime("%Y%m%d-%H%M")
    response["Content-Disposition"] = f'attachment; filename="jurnal-{institution.slug}-{stamp}.csv"'
    response.write("﻿")  # Excel o'zbekcha harflarni to'g'ri ochishi uchun
    writer = csv.writer(response)
    writer.writerow(["Vaqt", "Kim", "Rol", "Amal", "Obyekt turi", "Obyekt", "O'zgarishlar", "IP", "Xesh"])
    for e in entries.iterator():
        changes = "; ".join(
            f"{c.get('label', k)}: {c.get('old', '')} → {c.get('new', '')}".strip()
            for k, c in (e.changes or {}).items()
        )
        writer.writerow(
            [
                timezone.localtime(e.created_at).strftime("%d.%m.%Y %H:%M:%S"),
                e.actor_repr,
                e.actor_role,
                e.get_action_display(),
                e.target_label,
                e.target_repr,
                changes,
                e.ip or "",
                e.hash,
            ]
        )
    return response


@login_required
def audit_log(request):
    """Harakatlar jurnali: OTM rektorati va administratori uchun, faqat o'qish."""
    if not request.user.is_institution_admin or request.institution is None:
        raise PermissionDenied
    entries = _filtered(request)
    if request.GET.get("format") == "csv":
        return _csv(entries, request.institution)
    integrity = None
    if request.GET.get("verify"):
        checked, broken = services.verify(request.institution.pk)
        integrity = {"checked": checked, "broken": broken}
    types = sorted(
        set(AuditLog.objects.exclude(target_type="").values_list("target_type", "target_label")),
        key=lambda pair: pair[1],
    )
    page = Paginator(entries, 50).get_page(request.GET.get("page"))
    query = request.GET.copy()
    query.pop("page", None)
    query.pop("verify", None)
    context = {
        "page": page,
        "actions": AuditLog.Action.choices,
        "types": types,
        "integrity": integrity,
        "filters": request.GET,
        "csv_query": (query.urlencode() + "&" if query else "") + "format=csv",
        "total": AuditLog.objects.count(),
    }
    return render(request, "web/audit/log.html", context)
