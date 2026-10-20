"""Iqtidorlar qidiruvi: so'rovnomadan profilga yozilgan qobiliyatlar bo'yicha talabani topish."""

from django.contrib import messages
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.accounts.models import Faculty, Tutor
from apps.profiles.models import Skill
from apps.surveys import skills
from apps.surveys import xlsx as x

from .common import management_required, paginate

XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _scope(user):
    faculties = Faculty.objects.order_by("name")
    tutors = Tutor.objects.filter(is_active=True).select_related("faculty").order_by("faculty__name", "full_name")
    if user.role == user.Role.DEAN and not user.is_superuser and user.faculty_id:
        faculties = faculties.filter(pk=user.faculty_id)
        tutors = tutors.filter(faculty_id=user.faculty_id)
    return list(faculties), list(tutors)


def _query(request, drop=None):
    query = request.GET.copy()
    query.pop("page", None)
    if drop:
        key, value = drop
        query.setlist(key, [v for v in query.getlist(key) if v != value])
    return query.urlencode()


@management_required
def talent_search(request):
    students, chosen = skills.search(request.user, request.GET)
    page = paginate(request, students, per_page=24)
    faculties, tutors = _scope(request.user)
    picked = {s.pk for s in chosen}
    popular = skills.popular(skills.students_for(request.user))
    for item in popular:
        item["active"] = item["id"] in picked
    context = {
        "page": page,
        "cards": skills.describe(page.object_list, chosen),
        "found": page.paginator.count,
        "chosen": [{"skill": s, "remove": _query(request, ("skill", str(s.pk)))} for s in chosen],
        "popular": popular,
        "all_skills": Skill.objects.filter(user_skills__user__in=skills.students_for(request.user))
        .distinct()
        .order_by("name"),
        "faculties": faculties,
        "tutors": tutors,
        "courses": range(1, 7),
        "filters": request.GET,
        "query": _query(request),
        "total": skills.students_for(request.user).filter(skills__isnull=False).distinct().count(),
    }
    return render(request, "web/talent/search.html", context)


@management_required
def talent_search_export(request):
    students, chosen = skills.search(request.user, request.GET)
    cards = skills.describe(students, chosen)
    sheet = x.Sheet("Iqtidorlar")
    head = ["№", "F.I.Sh.", "Fakultet", "Kurs", "Guruh", "Tyutor", "Telefon", "Login", "Qobiliyatlari"]
    sheet.widths = [6, 30, 28, 7, 12, 26, 18, 20, 70]
    subtitle = (
        "Qidiruv: " + ", ".join(s.name for s in chosen) + " · " if chosen else ""
    ) + f"{len(cards)} nafar talaba · {timezone.localtime():%d.%m.%Y %H:%M}"
    x.title_block(sheet, "Iqtidorlar qidiruvi natijasi", subtitle, len(head))
    header = sheet.add([(h, "head") for h in head], height=30)
    for number, card in enumerate(cards, 1):
        z = "_z" if number % 2 == 0 else ""
        user = card["user"]
        sheet.add(
            [
                (number, f"num{z}"),
                (" ".join(filter(None, [user.last_name, user.first_name])) or user.username, f"bold{z}"),
                (user.faculty.name if user.faculty_id else "", f"text{z}"),
                (user.course or "", f"num{z}"),
                (card["group"], f"num{z}"),
                (card["tutor"].full_name if card["tutor"] else "", f"text{z}"),
                (card["phone"], f"text{z}"),
                (user.username, f"text{z}"),
                (", ".join(s["name"] for s in card["skills"]), f"text{z}"),
            ]
        )
    sheet.freeze = (header, 2)
    sheet.filter = f"A{header}:{x.col_name(len(head) - 1)}{header + max(len(cards), 1)}"
    institution = request.institution.name if request.institution else "Talent Hub"
    content = x.workbook([sheet], title="Iqtidorlar qidiruvi", author=institution)
    response = HttpResponse(content, content_type=XLSX)
    response["Content-Disposition"] = f'attachment; filename="iqtidorlar-{timezone.localtime():%Y%m%d-%H%M}.xlsx"'
    return response


@management_required
@require_POST
def talent_search_sync(request):
    if request.user.is_institution_admin:
        added = skills.sync_all()
        messages.success(request, f"So'rovnoma javoblaridan profillarga {added} ta yangi qobiliyat yozildi")
    return redirect(reverse("web:talent-search"))
