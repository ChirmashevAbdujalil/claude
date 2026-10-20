"""Tyutor kabineti: tyutor o'z talabalarini, so'rovnomalardagi qamrovni va login-parollarni ko'radi."""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models import Count, Q
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.accounts.models import Tutor, User
from apps.audit import services as audit
from apps.audit.models import AuditLog
from apps.surveys import accounts
from apps.surveys import docx as word
from apps.surveys.models import IssuedAccount, Response, Survey

from ..qr import qr_svg

DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


def _own_tutor(request):
    tutor = Tutor.objects.filter(user=request.user, is_active=True).select_related("faculty").first()
    if tutor is None:
        raise Http404("Tyutor kabineti topilmadi")
    return tutor


def _viewable_tutor(request, pk):
    """Rahbariyat istalgan tyutor kabinetini ko'radi (dekan faqat o'z fakultetinikini)."""
    user = request.user
    if not user.is_management:
        raise PermissionDenied
    tutor = get_object_or_404(Tutor.objects.select_related("faculty", "user"), pk=pk)
    if user.role == User.Role.DEAN and not user.is_superuser and user.faculty_id != tutor.faculty_id:
        raise PermissionDenied
    return tutor


def _students(tutor):
    """Tyutorning talabalari: so'rovnomada uni belgilaganlar (har bir talaba bir marta)."""
    responses = Response.objects.filter(tutor=tutor).select_related("user", "survey").order_by("-submitted_at")
    accounts_by_user = {
        a.user_id: a
        for a in IssuedAccount.objects.filter(tutor=tutor, user__role=User.Role.STUDENT).select_related("user")
    }
    people = {}
    for response in responses:
        key = response.user_id or f"name:{response.full_name.strip().lower()}|{response.group}"
        person = people.get(key)
        if person is None:
            person = people[key] = {
                "name": response.display_name,
                "user": response.user,
                "group": response.group,
                "course": response.course,
                "phone": response.phone,
                "surveys": [],
                "last": response.submitted_at,
                "account": accounts_by_user.get(response.user_id),
            }
        if response.survey.title not in person["surveys"]:
            person["surveys"].append(response.survey.title)
    return sorted(people.values(), key=lambda p: (p["group"] or "~", p["name"]))


def _cabinet(request, tutor, *, preview=False):
    students = _students(tutor)
    group_filter = request.GET.get("group", "")
    groups = {}
    for person in students:
        groups.setdefault(person["group"] or "Guruhsiz", []).append(person)
    shown = [p for p in students if not group_filter or (p["group"] or "Guruhsiz") == group_filter]

    base = reverse("web:survey-fill", args=["TOKEN"]).replace("TOKEN/", "")
    surveys = []
    open_surveys = Survey.objects.filter(status=Survey.Status.OPEN, collect_identity=True).annotate(
        mine=Count("responses", filter=Q(responses__tutor=tutor)),
        faculty_total=Count("responses", filter=Q(responses__faculty_id=tutor.faculty_id)),
    )
    for survey in open_surveys.order_by("-published_at", "-created_at"):
        if survey.is_expired:
            continue
        url = request.build_absolute_uri(f"{base}{survey.token}/?t={tutor.pk}")
        surveys.append(
            {
                "survey": survey,
                "url": url,
                "qr": qr_svg(url, size=160, label=f"«{survey.title}»: {tutor.full_name} havolasi"),
                "message": (
                    f"Hurmatli talabalar! «{survey.title}» so'rovnomasini to'ldiring. Ro'yxatdan o'tish shart emas, "
                    f"bir necha daqiqa vaqt oladi. Tyutoringiz: {tutor.full_name}.\n{url}"
                ),
            }
        )
    accounts_list = [p["account"] for p in students if p["account"]]
    context = {
        "tutor": tutor,
        "preview": preview,
        "students": shown,
        "groups": sorted(((name, len(items)) for name, items in groups.items()), key=lambda g: g[0]),
        "group_filter": group_filter,
        "surveys": surveys,
        "totals": {
            "students": len(students),
            "groups": len(groups),
            "accounts": len(accounts_list),
            "waiting": sum(1 for a in accounts_list if a.initial_password),
            "logged": sum(1 for a in accounts_list if not a.initial_password),
            "week": sum(1 for p in students if (timezone.now() - p["last"]).days < 7),
        },
    }
    return render(request, "web/tutor/cabinet.html", context)


@login_required
def cabinet(request):
    tutor = Tutor.objects.filter(user=request.user, is_active=True).select_related("faculty").first()
    if tutor is not None:
        return _cabinet(request, tutor)
    return _choose(request)


def _choose(request):
    """Tyutor bo'lmagan foydalanuvchi: rahbariyatga barcha tyutor kabinetlari ro'yxati, boshqalarga izoh."""
    user = request.user
    if not user.is_management:
        return render(request, "web/tutor/choose.html", {"groups": None}, status=403)
    tutors = (
        Tutor.objects.filter(is_active=True)
        .select_related("faculty", "user")
        .annotate(students=Count("responses"))
        .order_by("faculty__name", "full_name")
    )
    if user.role == User.Role.DEAN and not user.is_superuser and user.faculty_id:
        tutors = tutors.filter(faculty_id=user.faculty_id)
    groups = {}
    for tutor in tutors:
        groups.setdefault(tutor.faculty, []).append(tutor)
    context = {
        "groups": list(groups.items()),
        "total": sum(len(items) for items in groups.values()),
        "with_login": sum(1 for items in groups.values() for t in items if t.user_id),
    }
    return render(request, "web/tutor/choose.html", context)


@login_required
def cabinet_view(request, pk):
    return _cabinet(request, _viewable_tutor(request, pk), preview=True)


@login_required
def cabinet_word(request):
    tutor = _own_tutor(request)
    layout = "cards" if request.GET.get("layout") == "cards" else "table"
    items = IssuedAccount.objects.filter(tutor=tutor, user__role=User.Role.STUDENT).select_related(
        "user", "user__faculty"
    )
    if request.GET.get("group"):
        items = items.filter(group=request.GET["group"])
    items = list(items.order_by("group", "user__last_name", "user__first_name"))
    rows = [
        {
            "name": " ".join(filter(None, [a.user.last_name, a.user.first_name])) or a.user.username,
            "faculty": a.user.faculty.name if a.user.faculty_id else "",
            "faculty_short": a.user.faculty.short_name if a.user.faculty_id else "",
            "course": a.user.course or "",
            "group": a.group,
            "phone": a.phone,
            "login": a.user.username,
            "password": a.initial_password,
        }
        for a in items
    ]
    institution = request.institution
    site = institution.base_url(request) if institution is not None else request.build_absolute_uri("/")
    site = site.replace("https://", "").replace("http://", "").rstrip("/")
    now = timezone.localtime()
    content = word.render(
        rows,
        layout=layout,
        institution=institution.name if institution else "Talent Hub",
        site=site,
        subtitle=f"Tyutor: {tutor.full_name} · {len(rows)} nafar talaba · {now:%d.%m.%Y %H:%M}",
        signature=f"Tyutor: {tutor.full_name}  ____________ (imzo)",
    )
    audit.record(
        AuditLog.Action.EXPORT,
        actor=request.user,
        actor_repr=request.user.username,
        actor_role="Tyutor",
        changes={
            "file": {"label": "Fayl", "new": "Tyutor talabalari login va parollari (Word)"},
            "count": {"label": "Talabalar soni", "new": str(len(rows))},
        },
    )
    response = HttpResponse(content, content_type=DOCX)
    response["Content-Disposition"] = f'attachment; filename="talabalarim-login-parollar-{now:%Y%m%d-%H%M}.docx"'
    return response


@login_required
@require_POST
def cabinet_reset(request, pk):
    """Tyutor o'z talabasi parolini unutsa, yangisini yaratadi."""
    tutor = _own_tutor(request)
    account = get_object_or_404(IssuedAccount, pk=pk, tutor=tutor, user__role=User.Role.STUDENT)
    password = accounts.reset_password(account)
    messages.success(request, f"{account.user.get_full_name() or account.user.username}: yangi parol — {password}")
    return redirect(reverse("web:tutor-cabinet") + "#talabalar")
