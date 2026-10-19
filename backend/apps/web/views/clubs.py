"""So'rovnoma natijasidan tuzilgan klublar: tuzish, boshqarish, a'zolarga xabar va talaba ko'radigan sahifa."""

from django import forms
from django.contrib import messages
from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import PermissionDenied
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from apps.surveys import clubs, exports
from apps.surveys import services as survey_services
from apps.surveys.models import Club, Survey

from ..forms import https_urls
from .common import management_required


class ClubForm(forms.ModelForm):
    class Meta:
        model = Club
        formfield_callback = https_urls
        fields = ["name", "emoji", "description", "mentor", "leader", "telegram_url"]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 3, "placeholder": "Klub maqsadi, uchrashuv vaqti, rejalar"}),
            "emoji": forms.TextInput(attrs={"maxlength": 8}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["mentor"].queryset = clubs.mentors()
        self.fields["mentor"].empty_label = "Biriktirilmagan"
        members = self.instance.members.filter(response__user__isnull=False).values_list("response__user_id", flat=True)
        self.fields["leader"].queryset = self.fields["leader"].queryset.model.objects.filter(pk__in=members)
        self.fields["leader"].empty_label = "Tanlanmagan"
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", "input")


def _club(request, pk, cid):
    club = get_object_or_404(
        Club.objects.select_related("survey", "question", "leader", "mentor"), pk=cid, survey_id=pk
    )
    return club


def _editable(request, survey):
    if not survey_services.can_edit(request.user, survey):
        raise PermissionDenied


@management_required
@require_POST
def clubs_create(request, pk):
    survey = get_object_or_404(Survey, pk=pk)
    _editable(request, survey)
    question = next((q for q in clubs.club_questions(survey) if str(q.pk) == request.POST.get("question")), None)
    back = f"{reverse('web:survey-results', args=[survey.pk])}?tab=clubs"
    if question is None:
        messages.error(request, "Klub tuzish uchun savolni tanlang")
        return redirect(back)
    values = request.POST.getlist("option") or None
    # Variantlar belgilangan bo'lsa, rahbariyat tanlovi hal qiladi; aks holda kamida 3 a'zoli variantlar
    minimum = 1 if values else clubs.MIN_MEMBERS
    result = clubs.form_clubs(
        survey, question, survey.responses.all(), by=request.user, values=values, min_members=minimum
    )
    if result["created"] or result["updated"]:
        text = f"Yangi klublar: {result['created']}"
        if result["updated"]:
            text += f", yangilangan: {result['updated']}"
        text += f". Qo'shilgan a'zolar: {result['members']}"
        messages.success(request, text)
    else:
        messages.error(request, "Klub tuzish uchun kamida bitta variantni belgilang")
    return redirect(f"{back}&cq={question.pk}")


@management_required
def club_detail(request, pk, cid):
    club = _club(request, pk, cid)
    can_edit = survey_services.can_edit(request.user, club.survey)
    form = ClubForm(request.POST or None, instance=club) if can_edit else None
    if request.method == "POST" and form is not None and form.is_valid():
        form.save()
        messages.success(request, "Klub saqlandi")
        return redirect("web:club-detail", pk=pk, cid=cid)
    members = list(club.members.select_related("response__faculty", "response__user").order_by("response__full_name"))
    registered = survey_services.in_registry([m.response for m in members])
    for member in members:
        member.in_registry = member.response.user_id in registered
    context = {
        "club": club,
        "survey": club.survey,
        "members": members,
        "stats": clubs.stats(club),
        "form": form,
        "can_edit": can_edit,
        "public_url": request.build_absolute_uri(reverse("web:club-page", args=[club.pk])),
        "others": club.survey.clubs.exclude(pk=club.pk).order_by("name"),
    }
    return render(request, "web/surveys/club.html", context)


@management_required
@require_POST
def club_action(request, pk, cid, action):
    club = _club(request, pk, cid)
    back = reverse("web:club-detail", args=[pk, cid])
    if action == "notify":
        title = request.POST.get("title", "").strip()[:200]
        body = request.POST.get("body", "").strip()[:500]
        if not title:
            messages.error(request, "Xabar sarlavhasini yozing")
            return redirect(back)
        sent = clubs.notify_members(club, f"{club.emoji} {title}", body)
        messages.success(request, f"Xabar {sent} nafar a'zoga yuborildi")
    elif action == "register":
        result = clubs.register_members(club, request.user)
        messages.success(request, f"Reyestrga qo'shildi: {result['added']}, oldin bor edi: {result['existing']}")
    else:
        _editable(request, club.survey)
        if action == "sync":
            added = clubs.sync(club, club.survey.responses.all())
            messages.success(request, f"Yangi a'zolar: {added}" if added else "Yangi a'zo topilmadi")
        elif action == "remove":
            club.members.filter(pk=request.POST.get("member")).delete()
            messages.success(request, "A'zo klubdan chiqarildi")
        elif action == "delete":
            survey_pk = club.survey_id
            club.delete()
            messages.success(request, "Klub o'chirildi")
            return redirect(f"{reverse('web:survey-results', args=[survey_pk])}?tab=clubs")
        else:
            raise Http404
    return redirect(back)


@management_required
def club_export(request, pk, cid):
    club = _club(request, pk, cid)
    if request.GET.get("format") == "csv":
        response = HttpResponse(clubs.members_csv(club), content_type="text/csv; charset=utf-8")
        response["Content-Disposition"] = f'attachment; filename="klub-{club.pk}-azolar.csv"'
        return response
    institution = request.institution.name if request.institution else "Talent Hub"
    response = HttpResponse(
        exports.club_workbook(club, institution=institution),
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    response["Content-Disposition"] = f'attachment; filename="klub-{club.pk}-azolar.xlsx"'
    return response


def club_page(request, cid):
    """A'zolar va rahbariyat ko'radigan klub sahifasi."""
    club = get_object_or_404(Club.objects.select_related("survey", "leader", "mentor"), pk=cid)
    user = request.user
    if not user.is_authenticated:
        return redirect_to_login(request.get_full_path(), reverse("web:login"))
    if not (user.is_management or clubs.is_member(club, user)):
        raise Http404
    members = club.members.select_related("response__faculty", "response__user").order_by("response__full_name")
    return render(request, "web/surveys/club_page.html", {"club": club, "members": members, "stats": clubs.stats(club)})
