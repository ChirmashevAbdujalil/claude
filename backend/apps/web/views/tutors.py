"""Tyutorlar: fakultetlarga biriktirish, qo'shish, o'chirish va Word jadvalidan yuklash."""

from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.accounts import tutors as tutor_services
from apps.accounts.models import Faculty, Tutor

from .saas import _settings_admin

MAX_UPLOAD = 5 * 1024 * 1024


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
    items = Tutor.objects.select_related("faculty").annotate(responses_count=Count("responses"))
    grouped = {}
    for tutor in items.order_by("faculty__name", "full_name"):
        grouped.setdefault(tutor.faculty, []).append(tutor)
    faculties = Faculty.objects.order_by("name")
    context = {
        "form": form,
        "groups": [(faculty, grouped.get(faculty, [])) for faculty in faculties],
        "total": items.count(),
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
