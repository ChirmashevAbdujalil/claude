"""Login va parollar: so'rovnomadan ochilgan talaba akkauntlari, Word ro'yxati va parolni almashtirish."""

from django.contrib import messages
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import PasswordChangeForm, SetPasswordForm
from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.accounts.models import Faculty, Tutor
from apps.audit import services as audit
from apps.audit.models import AuditLog
from apps.surveys import accounts
from apps.surveys import docx as word
from apps.surveys.models import IssuedAccount, Survey

from .common import management_required, paginate

ORDER = ("user__faculty__name", "user__course", "group", "user__last_name", "user__first_name")
TUTOR_ORDER = (
    "user__faculty__name",
    "tutor__full_name",
    "user__course",
    "group",
    "user__last_name",
    "user__first_name",
)
LAYOUTS = {"table": "jadval", "cards": "kartochkalar", "tutors": "tyutorlar bo'yicha"}


def _filtered(request):
    items = accounts.visible_to(request.user)
    params = request.GET
    if params.get("q"):
        q = params["q"].strip()
        items = items.filter(
            Q(user__first_name__icontains=q)
            | Q(user__last_name__icontains=q)
            | Q(user__username__icontains=q)
            | Q(phone__icontains=q)
            | Q(group__icontains=q)
        )
    if params.get("faculty", "").isdigit():
        items = items.filter(user__faculty_id=params["faculty"])
    if params.get("course", "").isdigit():
        items = items.filter(user__course=params["course"])
    if params.get("group"):
        items = items.filter(group__iexact=params["group"].strip())
    if params.get("tutor", "").isdigit():
        items = items.filter(tutor_id=params["tutor"])
    elif params.get("tutor") == "none":
        items = items.filter(tutor__isnull=True)
    if params.get("survey", "").isdigit():
        items = items.filter(survey_id=params["survey"])
    if params.get("status") == "waiting":
        items = items.exclude(initial_password="")
    elif params.get("status") == "active":
        items = items.filter(initial_password="")
    return items


def _query(request):
    query = request.GET.copy()
    query.pop("page", None)
    return query.urlencode()


@management_required
def credentials(request):
    base = accounts.visible_to(request.user)
    items = _filtered(request).order_by(*ORDER)
    faculties = Faculty.objects.order_by("name")
    tutors = Tutor.objects.filter(is_active=True).select_related("faculty").order_by("faculty__name", "full_name")
    if request.user.role == request.user.Role.DEAN and request.user.faculty_id:
        faculties = faculties.filter(pk=request.user.faculty_id)
        tutors = tutors.filter(faculty_id=request.user.faculty_id)
    context = {
        "page": paginate(request, items, per_page=50),
        "filters": request.GET,
        "query": _query(request),
        "faculties": faculties,
        "tutors": list(tutors),
        "courses": range(1, 7),
        "surveys": Survey.objects.filter(issued_accounts__isnull=False).distinct().order_by("-created_at"),
        "groups": base.exclude(group="").order_by("group").values_list("group", flat=True).distinct(),
        "totals": {
            "all": base.count(),
            "waiting": base.exclude(initial_password="").count(),
            "active": base.filter(initial_password="").count(),
            "today": base.filter(created_at__date=timezone.localdate()).count(),
        },
        "pending": accounts.pending_surveys() if request.user.is_institution_admin else [],
        "found": items.count(),
    }
    return render(request, "web/surveys/credentials.html", context)


@management_required
def credentials_word(request):
    layout = request.GET.get("layout") if request.GET.get("layout") in LAYOUTS else "table"
    items = list(_filtered(request).order_by(*(TUTOR_ORDER if layout == "tutors" else ORDER)))
    institution = request.institution
    site = institution.base_url(request) if institution is not None else request.build_absolute_uri("/")
    site = site.replace("https://", "").replace("http://", "").rstrip("/")
    rows = [
        {
            "name": " ".join(filter(None, [a.user.last_name, a.user.first_name])) or a.user.username,
            "faculty": a.user.faculty.name if a.user.faculty_id else "",
            "faculty_short": a.user.faculty.short_name if a.user.faculty_id else "",
            "course": a.user.course or "",
            "group": a.group,
            "tutor": a.tutor.full_name if a.tutor_id else "",
            "phone": a.phone,
            "login": a.user.username,
            "password": a.initial_password,
        }
        for a in items
    ]
    now = timezone.localtime()
    subtitle = f"{institution.name if institution else ''} · {len(rows)} nafar talaba · {now:%d.%m.%Y %H:%M}"
    signature = f"Ro'yxatni tayyorladi: {request.user.get_full_name() or request.user.username}  ____________ (imzo)"
    content = word.render(
        rows,
        layout=layout,
        institution=institution.name if institution else "Talent Hub",
        site=site,
        subtitle=subtitle,
        signature=signature,
        date=f"{now:%d.%m.%Y}",
    )
    audit.record(
        AuditLog.Action.EXPORT,
        actor=request.user,
        actor_repr=request.user.username,
        actor_role="Platforma egasi" if request.user.is_superuser else request.user.get_role_display(),
        changes={
            "file": {
                "label": "Fayl",
                "new": f"Login va parollar (Word, {LAYOUTS[layout]})",
            },
            "count": {"label": "Talabalar soni", "new": str(len(rows))},
        },
    )
    response = HttpResponse(
        content, content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )
    name = {"cards": "login-parollar-kartochkalar", "tutors": "login-parollar-tyutorlar"}.get(layout, "login-parollar")
    response["Content-Disposition"] = f'attachment; filename="{name}-{now:%Y%m%d-%H%M}.docx"'
    return response


@management_required
@require_POST
def credentials_reset(request, pk):
    account = get_object_or_404(accounts.visible_to(request.user), pk=pk)
    accounts.reset_password(account)
    messages.success(request, f"{account.user.get_full_name() or account.user.username}: yangi parol yaratildi")
    return redirect(request.POST.get("next") or reverse("web:credentials"))


@management_required
@require_POST
def credentials_provision(request, pk):
    if not request.user.is_institution_admin:
        return redirect("web:credentials")
    survey = get_object_or_404(Survey, pk=pk)
    result = accounts.provision_survey(survey)
    text = f"«{survey.title}»: {result['created']} ta yangi akkaunt ochildi"
    if result["linked"]:
        text += f", {result['linked']} ta javob mavjud akkauntga bog'landi"
    if result["skipped"]:
        text += f", {result['skipped']} ta o'tkazib yuborildi (ism yo'q yoki talabalar limiti tugagan)"
    messages.success(request, text)
    return redirect(f"{reverse('web:credentials')}?survey={survey.pk}")


@login_required
def password_change(request):
    account = IssuedAccount.objects.filter(user=request.user).first()
    first_time = bool(account and account.must_change_password)
    form_class = SetPasswordForm if first_time else PasswordChangeForm
    form = form_class(request.user, request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        update_session_auth_hash(request, user)
        accounts.password_changed(user)
        messages.success(request, "Parolingiz saqlandi. Endi shu parol bilan kirasiz")
        return redirect("web:dashboard")
    for field in form.fields.values():
        field.widget.attrs.setdefault("class", "input")
    form.fields[
        "new_password1"
    ].help_text = "Kamida 8 belgi. Faqat raqamdan iborat bo'lmasin va ismingiz yoki loginingizga o'xshamasin"
    form.fields["new_password2"].help_text = "Yangi parolni yana bir marta yozing"
    return render(request, "web/auth/password.html", {"form": form, "first_time": first_time})
