"""SaaS sahifalari: platforma taqdimoti va ulanish arizasi, platforma egasi paneli,
OTM sozlamalari va OTMlararo liga."""

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required, user_passes_test
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.accounts.models import Faculty
from apps.tenants import plans
from apps.tenants import services as tenant_services
from apps.tenants.context import unscoped
from apps.tenants.models import Institution, InstitutionRequest

from ..context_processors import branding
from ..forms import FacultyForm, InstitutionRequestForm, InstitutionSettingsForm

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
    context["requests"] = InstitutionRequest.objects.filter(status=InstitutionRequest.Status.NEW)[:20]
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
        messages.success(
            request,
            f"«{institution.short_name}» ulandi. Manzil: {institution.base_url(request)} · "
            f"Login: {admin.username} · Parol: {password} (faqat hozir ko'rinadi, OTMga yetkazing)",
        )
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
    if request.method == "POST":
        if request.POST.get("form") == "settings" and form.is_valid():
            form.save()
            messages.success(request, "OTM sozlamalari saqlandi")
            return redirect("web:institution-settings")
        if request.POST.get("form") == "faculty" and faculty_form.is_valid():
            faculty = faculty_form.save()
            messages.success(request, f"«{faculty.name}» qo'shildi")
            return redirect("web:institution-settings")
    students = tenant_services.student_count(institution)
    limit = institution.student_limit
    context = {
        "form": form,
        "faculty_form": faculty_form,
        "faculties": Faculty.objects.all(),
        "plan": institution.plan_info,
        "plans": _plans(),
        "students": students,
        "limit": limit,
        "usage": round(students * 100 / limit) if limit else None,
        "site_url": institution.base_url(request),
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
