"""SaaS sahifalari: platforma taqdimoti va ulanish arizasi, platforma egasi paneli,
OTM sozlamalari va OTMlararo liga."""

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required, user_passes_test
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.accounts.models import Faculty
from apps.billing import services as billing_services
from apps.billing.models import Invoice
from apps.tenants import plans
from apps.tenants import services as tenant_services
from apps.tenants.context import unscoped
from apps.tenants.models import Institution, InstitutionRequest

from ..context_processors import branding
from ..forms import CuratorForm, FacultyForm, InstitutionRequestForm, InstitutionSettingsForm

User = get_user_model()


def _plans():
    return [
        {
            "key": key,
            **plan,
            "feature_list": [label for feature, label in plans.FEATURE_LABELS.items() if feature in plan["features"]],
        }
        for key, plan in plans.PLANS.items()
    ]


def saas_landing(request):
    """Platforma taqdimoti, tariflar va «OTMingizni ulang» arizasi."""
    form = InstitutionRequestForm(request.POST or None, initial={"plan": request.GET.get("plan", "pilot")})
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Ariza qabul qilindi! 1-2 ish kuni ichida siz bilan bog'lanamiz.")
        return redirect("/saas/#ariza")
    with unscoped():
        connected = list(Institution.objects.filter(is_active=True).order_by("name"))
    context = branding(None) | {
        "form": form,
        "plans": _plans(),
        "connected": connected,
        "students_total": tenant_services.total_students(),
    }
    return render(request, "web/saas/landing.html", context)


@user_passes_test(lambda u: u.is_active and u.is_superuser, login_url="web:login")
def platform_dashboard(request):
    """Platforma egasi uchun: barcha OTMlar, tariflar, faollik va yangi arizalar."""
    context = branding(None) | tenant_services.platform_overview()
    for row in context["institutions"]:
        row["url"] = row["obj"].base_url(request)
    # Yangi yaratilgan yoki yangilangan parol: faqat bir marta ko'rsatiladi
    context["credentials"] = request.session.pop("platform_credentials", None)
    context["requests"] = InstitutionRequest.objects.filter(status=InstitutionRequest.Status.NEW)[:20]
    context["payments"] = Invoice.objects.filter(status=Invoice.Status.PAID).select_related("institution")[:10]
    month_start = timezone.localdate().replace(day=1)
    context["revenue_month"] = sum(
        Invoice.objects.filter(status=Invoice.Status.PAID, paid_at__date__gte=month_start).values_list(
            "amount", flat=True
        )
    )
    return render(request, "web/saas/platform.html", context)


@user_passes_test(lambda u: u.is_active and u.is_superuser, login_url="web:login")
@require_POST
def platform_approve(request, pk):
    request_obj = get_object_or_404(InstitutionRequest, pk=pk)
    try:
        institution, admin, password = tenant_services.approve_request(request_obj)
    except tenant_services.TenantError as exc:
        messages.error(request, str(exc))
    else:
        _show_credentials(request, institution, admin, password, f"«{institution.short_name}» ulandi")
    return redirect("web:platform")


def _show_credentials(request, institution, user, password, title):
    request.session["platform_credentials"] = {
        "title": title,
        "institution": institution.short_name,
        "url": f"{institution.base_url(request)}/login/",
        "username": user.username,
        "password": password,
    }


@user_passes_test(lambda u: u.is_active and u.is_superuser, login_url="web:login")
@require_POST
def platform_reset_password(request, pk):
    """OTM xodimiga yangi parol: eski parolni ko'rsatib bo'lmaydi, chunki bazada faqat hash saqlanadi."""
    with unscoped():
        user = get_object_or_404(
            User.objects.select_related("institution"), pk=pk, role__in=User.REVIEWER_ROLES, is_superuser=False
        )
    password = tenant_services.reset_password(user)
    _show_credentials(request, user.institution, user, password, f"{user.username}: parol yangilandi")
    return redirect("web:platform")


def _settings_admin(request):
    if not request.user.is_institution_admin or request.institution is None:
        raise PermissionDenied
    return request.institution


@login_required
def institution_settings(request):
    institution = _settings_admin(request)
    form = InstitutionSettingsForm(
        request.POST if request.POST.get("form") == "settings" else None,
        request.FILES or None,
        instance=institution,
    )
    faculty_form = FacultyForm(request.POST if request.POST.get("form") == "faculty" else None)
    curator_form = CuratorForm(
        request.POST if request.POST.get("form") == "curator" else None,
        request.FILES if request.POST.get("form") == "curator" else None,
        instance=institution,
        prefix="curator",
    )
    if request.method == "POST":
        if request.POST.get("form") == "curator" and curator_form.is_valid():
            curator_form.save()
            messages.success(request, "Mas'ul shaxs bloki saqlandi")
            return redirect(f"{reverse('web:institution-settings')}#masul")
        if request.POST.get("form") == "settings" and form.is_valid():
            form.save()
            messages.success(request, "OTM sozlamalari saqlandi")
            return redirect("web:institution-settings")
        if request.POST.get("form") == "contingent":
            changed = 0
            for faculty in Faculty.objects.all():
                raw = request.POST.get(f"contingent-{faculty.pk}", "").strip()
                value = int(raw) if raw.isdigit() and 0 < int(raw) <= 100000 else None
                if faculty.contingent != value:
                    faculty.contingent = value
                    faculty.save(update_fields=["contingent"])
                    changed += 1
            messages.success(request, "Talabalar soni saqlandi" if changed else "O'zgarish yo'q")
            return redirect(f"{reverse('web:institution-settings')}#fakultetlar")
        if request.POST.get("form") == "faculty" and faculty_form.is_valid():
            faculty = faculty_form.save()
            messages.success(request, f"«{faculty.name}» qo'shildi")
            return redirect("web:institution-settings")
    students = tenant_services.student_count(institution)
    limit = institution.student_limit
    context = {
        "form": form,
        "faculty_form": faculty_form,
        "curator_form": curator_form,
        "faculties": Faculty.objects.all(),
        "plan": institution.plan_info,
        "plans": _plans(),
        "students": students,
        "limit": limit,
        "usage": round(students * 100 / limit) if limit else None,
        "site_url": institution.base_url(request),
        "periods": billing_services.PERIODS,
        "paid_plans": [p for p in _plans() if p["price"]],
        "invoices": Invoice.objects.filter(institution=institution)[:10],
        "payments_on": billing_services.payme_enabled() or billing_services.click_enabled(),
    }
    return render(request, "web/saas/settings.html", context)


@login_required
@require_POST
def faculty_delete(request, pk):
    _settings_admin(request)
    faculty = get_object_or_404(Faculty, pk=pk)
    if User.objects.filter(faculty=faculty).exists():
        messages.error(request, "Bu fakultetda talabalar bor: avval ularni boshqa fakultetga o'tkazing")
    else:
        faculty.delete()
        messages.info(request, "Fakultet o'chirildi")
    return redirect("web:institution-settings")


@login_required
def league(request):
    rows = tenant_services.league()
    mine = next((i for i, row in enumerate(rows) if row["obj"].pk == request.institution.pk), None)
    return render(request, "web/saas/league.html", {"rows": rows, "my_index": mine})
