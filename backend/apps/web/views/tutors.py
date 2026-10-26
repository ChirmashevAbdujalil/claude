"""Tyutorlar: fakultetlarga biriktirish, qo'shish, o'chirish va Word jadvalidan yuklash."""

from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.accounts import tutor_pdf
from apps.accounts import tutors as tutor_services
from apps.accounts.models import Faculty, Tutor
from apps.audit import services as audit
from apps.audit.models import AuditLog
from apps.surveys import docx as word

from .saas import _settings_admin

MAX_UPLOAD = 5 * 1024 * 1024
DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
PDF = "application/pdf"


class TutorForm(forms.ModelForm):
    class Meta:
        model = Tutor
        fields = ["faculty", "full_name", "phone"]
        labels = {"full_name": "Familiya, ism"}
        widgets = {
            "full_name": forms.TextInput(attrs={"placeholder": "Yaxshiboyev Davronbek"}),
            "phone": forms.TextInput(attrs={"placeholder": "+998 90 123 45 67", "inputmode": "tel"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["faculty"].queryset = Faculty.objects.order_by("name")
        self.fields["faculty"].empty_label = "Fakultetni tanlang"

    def clean_full_name(self):
        return tutor_services.clean_name(self.cleaned_data["full_name"])

    def clean(self):
        cleaned = super().clean()
        faculty, name = cleaned.get("faculty"), cleaned.get("full_name")
        if faculty and name and Tutor.objects.filter(faculty=faculty, full_name__iexact=name).exists():
            self.add_error("full_name", "Bu tyutor shu fakultetda bor")
        return cleaned


@login_required
def tutors(request):
    _settings_admin(request)
    form = TutorForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        tutor = form.save()
        messages.success(request, f"{tutor.full_name} «{tutor.faculty.short_name}» fakultetiga biriktirildi")
        return redirect("web:tutors")
    items = Tutor.objects.select_related("faculty", "user").annotate(responses_count=Count("responses"))
    grouped = {}
    for tutor in items.order_by("faculty__name", "full_name"):
        grouped.setdefault(tutor.faculty, []).append(tutor)
    faculties = Faculty.objects.order_by("name")
    context = {
        "form": form,
        "groups": [(faculty, grouped.get(faculty, [])) for faculty in faculties],
        "total": items.count(),
        "with_accounts": items.filter(user__isnull=False).count(),
    }
    return render(request, "web/saas/tutors.html", context)


@login_required
@require_POST
def tutor_delete(request, pk):
    _settings_admin(request)
    tutor = get_object_or_404(Tutor, pk=pk)
    tutor.delete()
    messages.info(request, f"{tutor.full_name} ro'yxatdan olib tashlandi (talabalar javoblari saqlanadi)")
    return redirect("web:tutors")


@login_required
@require_POST
def tutor_import(request):
    _settings_admin(request)
    upload = request.FILES.get("file")
    if upload is None or not upload.name.lower().endswith(".docx"):
        messages.error(request, "Word (.docx) faylni tanlang")
        return redirect("web:tutors")
    if upload.size > MAX_UPLOAD:
        messages.error(request, "Fayl hajmi 5 MB dan oshmasin")
        return redirect("web:tutors")
    try:
        result = tutor_services.import_rows(tutor_services.read_docx_rows(upload))
    except tutor_services.TutorImportError as exc:
        messages.error(request, str(exc))
        return redirect("web:tutors")
    text = f"Yangi tyutorlar: {result['added']}, oldin bor edi: {result['existing']}"
    if result["unknown"]:
        text += f". Fakulteti topilmadi: {', '.join(result['unknown'][:5])}"
    messages.success(request, text)
    return redirect("web:tutors")


# ---------------------------------------------------------------- tyutor kabineti: loginlar


@login_required
@require_POST
def tutor_account(request, pk):
    """Bitta tyutorga login ochadi yoki yangi parol beradi."""
    _settings_admin(request)
    tutor = get_object_or_404(Tutor.objects.select_related("faculty", "user"), pk=pk)
    if tutor.user_id:
        password = tutor_services.reset_account(tutor)
        messages.success(request, f"{tutor.full_name}: yangi parol — {password} (login: {tutor.user.username})")
    else:
        account, _ = tutor_services.create_account(tutor)
        login, password = account.user.username, account.initial_password
        messages.success(request, f"{tutor.full_name} uchun kabinet ochildi. Login: {login}, parol: {password}")
    return redirect("web:tutors")


@login_required
@require_POST
def tutor_accounts_all(request):
    _settings_admin(request)
    created = 0
    for tutor in Tutor.objects.filter(is_active=True, user__isnull=True).select_related("faculty"):
        created += tutor_services.create_account(tutor)[1]
    messages.success(request, f"{created} ta tyutorga kabinet ochildi. Login va parollarni Word faylda yuklab oling")
    return redirect("web:tutors")


def _account_export(request, kind):
    """Hali kirmagan tyutorlarning login-parollari: Word yoki PDF. Hech kim qolmagan bo'lsa None."""
    _settings_admin(request)
    tutors = list(
        Tutor.objects.filter(is_active=True, user__isnull=False)
        .select_related("faculty", "user")
        .order_by("faculty__name", "full_name")
    )
    rows = [row for row in tutor_services.account_rows(tutors) if row["password"]]  # hali kirmaganlar
    if not rows:
        messages.info(request, "Barcha tyutorlar o'z parolini o'rnatgan: tarqatiladigan boshlang'ich parol yo'q")
        return None
    institution = request.institution
    site = institution.base_url(request) if institution is not None else request.build_absolute_uri("/")
    site = site.replace("https://", "").replace("http://", "").rstrip("/")
    now = timezone.localtime()
    render = tutor_pdf.render if kind == "pdf" else word.tutor_accounts
    content = render(
        rows,
        institution=institution.name if institution else "Talent Hub",
        site=site,
        subtitle=f"{len(rows)} nafar tyutor · {now:%d.%m.%Y %H:%M}",
    )
    audit.record(
        AuditLog.Action.EXPORT,
        actor=request.user,
        actor_repr=request.user.username,
        actor_role="Platforma egasi" if request.user.is_superuser else request.user.get_role_display(),
        changes={
            "file": {"label": "Fayl", "new": f"Tyutorlar login va parollari ({'PDF' if kind == 'pdf' else 'Word'})"},
            "count": {"label": "Tyutorlar soni", "new": str(len(rows))},
        },
    )
    response = HttpResponse(content, content_type=PDF if kind == "pdf" else DOCX)
    name = f"tyutorlar-login-parollar-{now:%Y%m%d-%H%M}.{'pdf' if kind == 'pdf' else 'docx'}"
    response["Content-Disposition"] = f'attachment; filename="{name}"'
    return response


@login_required
def tutor_accounts_word(request):
    return _account_export(request, "docx") or redirect("web:tutors")


@login_required
def tutor_accounts_pdf(request):
    return _account_export(request, "pdf") or redirect("web:tutors")
