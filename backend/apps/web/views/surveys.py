"""So'rovnomalar: konstruktor, ommaviy to'ldirish sahifasi, natijalar, eksport va iqtidorlar reyestriga qo'shish."""

import json
import re
import secrets
import shutil
import tempfile
import zipfile
from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import Count, Q
from django.http import FileResponse, Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_POST

from apps.accounts.models import Faculty, Tutor
from apps.arena.models import PointTransaction
from apps.audit import services as audit
from apps.audit.models import AuditLog
from apps.surveys import analytics, clubs, exports, services, word_report
from apps.surveys import files as file_rules
from apps.surveys.models import IssuedAccount, Question, Response, ResponseFile, Survey
from apps.surveys.services import SurveyError
from apps.talent.tracks import ICONS, Track

from ..forms import SurveyForm, SurveyIdentityForm
from ..qr import qr_svg
from .common import management_required, paginate

BROWSER_COOKIE = "th_sv"
BROWSER_COOKIE_AGE = 365 * 24 * 3600


def _editable(request, pk):
    survey = get_object_or_404(Survey, pk=pk)
    if not services.can_edit(request.user, survey):
        raise PermissionDenied
    return survey


def _fill_url(request, survey):
    return request.build_absolute_uri(reverse("web:survey-fill", args=[survey.token]))


def _share(request, survey, tutor=None):
    url = _fill_url(request, survey)
    if tutor is not None:
        url += f"?t={tutor.pk}"
    return {"url": url, "qr": qr_svg(url, label=f"«{survey.title}» so'rovnomasining QR kodi")}


def _link_tutor(request):
    """Tyutorning shaxsiy havolasidagi (?t=<id>) faol tyutor."""
    value = request.GET.get("t", "")
    if not value.isdigit():
        return None
    return Tutor.objects.filter(pk=value, is_active=True).select_related("faculty").first()


def _filtered(request, survey):
    responses = services.responses_for(request.user, survey)
    params = request.GET
    if params.get("faculty", "").isdigit():
        responses = responses.filter(faculty_id=params["faculty"])
    if params.get("course", "").isdigit():
        responses = responses.filter(course=params["course"])
    if params.get("group"):
        responses = responses.filter(group__iexact=params["group"].strip())
    if params.get("tutor", "").isdigit():
        responses = responses.filter(tutor_id=params["tutor"])
    if params.get("q"):
        q = params["q"].strip()
        responses = responses.filter(
            Q(full_name__icontains=q) | Q(user__username__icontains=q) | Q(group__icontains=q) | Q(phone__icontains=q)
        )
    if params.get("linked") == "1":
        responses = responses.filter(user__isnull=False)
    return analytics.apply_conditions(responses, analytics.parse_conditions(survey, params.getlist("answer")))


def _without(request, key, value):
    """Joriy so'rovdan bitta filtr qiymatini olib tashlagan query string."""
    query = request.GET.copy()
    query.setlist(key, [v for v in query.getlist(key) if v != value])
    query.pop("page", None)
    return query.urlencode()


def _filter_qs(request):
    query = request.GET.copy()
    for key in ("tab", "page", "cq", "x", "y"):
        query.pop(key, None)
    return query.urlencode()


# ---------------------------------------------------------------- ro'yxat va yaratish


@login_required
def survey_list(request):
    user = request.user
    answered = Response.objects.filter(user=user).select_related("survey").order_by("-submitted_at")
    context = {
        "open_surveys": services.open_for(user).order_by("closes_at", "-published_at"),
        "answered": answered[:10],
        "my_clubs": clubs.clubs_of(user),
    }
    if user.is_management:
        surveys = services.management_list()
        if request.GET.get("status") in Survey.Status.values:
            surveys = surveys.filter(status=request.GET["status"])
        context |= {
            "page": paginate(request, surveys, per_page=20),
            "templates": services.TEMPLATES,
            "status_filter": request.GET.get("status", ""),
            "statuses": Survey.Status.choices,
            "totals": {
                "surveys": Survey.objects.count(),
                "open": Survey.objects.filter(status=Survey.Status.OPEN).count(),
                "responses": Response.objects.count(),
                "today": Response.objects.filter(submitted_at__date=timezone.localdate()).count(),
            },
        }
    return render(request, "web/surveys/list.html", context)


@management_required
@require_POST
def survey_create(request):
    survey = services.create_survey(request.user, request.POST.get("template", "blank"))
    messages.success(request, "So'rovnoma yaratildi. Savollarni tahrirlang va e'lon qiling")
    return redirect("web:survey-builder", pk=survey.pk)


@management_required
@require_POST
def survey_duplicate(request, pk):
    survey = get_object_or_404(Survey, pk=pk)
    copy = services.duplicate(survey, request.user)
    messages.success(request, "Nusxa yaratildi")
    return redirect("web:survey-builder", pk=copy.pk)


@management_required
@require_POST
def survey_delete(request, pk):
    survey = _editable(request, pk)
    title = survey.title
    survey.delete()
    messages.success(request, f"«{title}» o'chirildi")
    return redirect("web:surveys")


# ---------------------------------------------------------------- konstruktor


@management_required
def survey_builder(request, pk):
    survey = _editable(request, pk)
    if request.method == "POST":
        form = SurveyForm(request.POST, instance=survey)
        schema_json = request.POST.get("schema", "[]")
        if form.is_valid():
            try:
                with transaction.atomic():
                    form.save()
                    services.save_schema(survey, schema_json)
            except SurveyError as exc:
                messages.error(request, str(exc))
            else:
                if request.POST.get("then") == "publish" and survey.status != Survey.Status.OPEN:
                    return _publish(request, survey, notify=request.POST.get("notify") == "1")
                messages.success(request, "Saqlandi")
                return redirect("web:survey-builder", pk=survey.pk)
        try:
            schema = json.loads(schema_json)
        except ValueError:
            schema = services.schema(survey)
    else:
        form = SurveyForm(instance=survey)
        schema = services.schema(survey)
    context = {
        "survey": survey,
        "form": form,
        "schema": schema,
        "kinds": [{"value": v, "label": label} for v, label in Question.Kind.choices],
        "share": _share(request, survey),
        "responses": survey.responses.count(),
    }
    return render(request, "web/surveys/builder.html", context)


def _publish(request, survey, notify):
    try:
        sent = services.publish(survey, notify_students=notify)
    except SurveyError as exc:
        messages.error(request, str(exc))
        return redirect("web:survey-builder", pk=survey.pk)
    text = "So'rovnoma e'lon qilindi: havola va QR kod orqali tarqating"
    if sent:
        text += f". {sent} nafar talabaga bildirishnoma yuborildi"
    messages.success(request, text)
    return redirect("web:survey-results", pk=survey.pk)


@management_required
@require_POST
def survey_status(request, pk):
    survey = _editable(request, pk)
    action = request.POST.get("action")
    if action == "publish":
        return _publish(request, survey, notify=request.POST.get("notify") == "1")
    if action == "close":
        services.close(survey)
        messages.success(request, "So'rovnoma yopildi: yangi javoblar qabul qilinmaydi")
    elif action == "draft":
        survey.status = Survey.Status.DRAFT
        survey.save(update_fields=["status", "updated_at"])
        messages.success(request, "Qoralamaga qaytarildi")
    return redirect(request.POST.get("next") or reverse("web:survey-results", args=[survey.pk]))


# ---------------------------------------------------------------- natijalar


@management_required
def survey_results(request, pk):
    survey = get_object_or_404(Survey.objects.select_related("created_by"), pk=pk)
    responses = _filtered(request, survey)
    tab = request.GET.get("tab", "summary")
    conditions = analytics.parse_conditions(survey, request.GET.getlist("answer"))
    for condition in conditions:
        condition["remove"] = _without(request, "answer", condition["raw"])
    summary = services.summary(survey, responses)
    context = {
        "survey": survey,
        "tab": tab,
        "filters": request.GET,
        "filter_qs": _filter_qs(request),
        "faculties": Faculty.objects.order_by("name"),
        "courses": range(1, 7),
        "groups": services.responses_for(request.user, survey)
        .exclude(group="")
        .order_by("group")
        .values_list("group", flat=True)
        .distinct(),
        "can_edit": services.can_edit(request.user, survey),
        "share": _share(request, survey),
        "tutors": _tutors_for(request.user),
        "summary": summary,
        "has_track": survey.questions.filter(kind=Question.Kind.TRACK).exists(),
        "conditions": conditions,
        "active_answers": {c["raw"] for c in conditions},
        "clubs_count": survey.clubs.count(),
    }
    if tab not in ("responses", "analysis", "clubs") and survey.collect_identity:
        context["registration"] = analytics.faculty_registration(responses, _faculties_for(request.user))
        tutors = _tutors_for(request.user)
        if tutors:
            context["tutor_stats"] = analytics.tutor_registration(responses, tutors)
    if tab == "analysis":
        context |= _analysis(request, survey, responses, summary)
    elif tab == "clubs":
        context |= _clubs_tab(request, survey)
    if tab == "responses":
        page = paginate(request, responses, per_page=30)
        registered = services.in_registry(page.object_list)
        for response in page.object_list:
            response.in_registry = response.user_id in registered
        context["page"] = page
    return render(request, "web/surveys/results.html", context)


def _faculties_for(user):
    faculties = Faculty.objects.order_by("name")
    if user.role == user.Role.DEAN and not user.is_superuser and user.faculty_id:
        faculties = faculties.filter(pk=user.faculty_id)
    return list(faculties)


def _tutors_for(user):
    tutors = Tutor.objects.filter(is_active=True).select_related("faculty").order_by("faculty__name", "full_name")
    if user.role == user.Role.DEAN and not user.is_superuser and user.faculty_id:
        tutors = tutors.filter(faculty_id=user.faculty_id)
    return list(tutors)


def _analysis(request, survey, responses, summary):
    questions = analytics.choice_questions(survey)
    by_id = {str(q.pk): q for q in questions}
    default_x = next((q for q in questions if q.kind == Question.Kind.TRACK), questions[0] if questions else None)
    x = by_id.get(request.GET.get("x", ""), default_x)
    dims = [(key, label) for key, label in analytics.dimensions(survey) if x is None or key != f"q{x.pk}"]
    y = request.GET.get("y") or (dims[0][0] if dims else "")
    timeline = analytics.timeline(responses)
    complete = analytics.completeness(survey, responses)
    return {
        "timeline": timeline,
        "complete": complete,
        "insights": analytics.insights(survey, responses, summary, timeline, complete),
        "x_questions": questions,
        "x": x,
        "dims": dims,
        "y": y,
        "crosstab": analytics.crosstab(survey, responses, x, y) if dims else None,
    }


def _clubs_tab(request, survey):
    questions = clubs.club_questions(survey)
    chosen = next((q for q in questions if str(q.pk) == request.GET.get("cq", "")), None)
    chosen = chosen or next(
        (q for q in questions if q.kind == Question.Kind.TRACK), questions[0] if questions else None
    )
    return {
        "club_rows": clubs.overview(survey),
        "club_questions": questions,
        "club_question": chosen,
        "club_preview": clubs.preview(survey, chosen, survey.responses.all()) if chosen else [],
        "club_min": clubs.MIN_MEMBERS,
    }


def _track_badge(track):
    return {"label": dict(Track.choices)[track], "icon": ICONS.get(track, "✨")} if track else None


@management_required
def survey_response(request, pk, rid):
    survey = get_object_or_404(Survey, pk=pk)
    visible = services.responses_for(request.user, survey)
    response = get_object_or_404(visible, pk=rid)
    items = services.answer_items(survey, response)
    answerable = [i for i in items if i["view"] != "section"]
    answered = sum(1 for i in answerable if i["view"] != "empty")
    registry = response.user.talent_profile if response.user_id and services.in_registry([response]) else None
    context = {
        "survey": survey,
        "response": response,
        "items": items,
        "answered": answered,
        "answerable": len(answerable),
        "completeness": round(answered * 100 / len(answerable)) if answerable else 0,
        "nav": services.neighbours(visible, response),
        "registry": registry,
        "track": _track_badge(services.track_of(survey, response)),
        "initials": "".join(part[0] for part in response.display_name.split()[:2]).upper() or "?",
        "hue": response.pk * 47 % 360,
        "can_edit": services.can_edit(request.user, survey),
    }
    return render(request, "web/surveys/response.html", context)


@management_required
@require_POST
def survey_response_delete(request, pk, rid):
    survey = _editable(request, pk)
    get_object_or_404(survey.responses, pk=rid).delete()
    messages.success(request, "Javob o'chirildi")
    return redirect(f"{reverse('web:survey-results', args=[survey.pk])}?tab=responses")


@management_required
def survey_file(request, pk, fid):
    """Javobga biriktirilgan fayl: faqat shu javobni ko'rish huquqi bor rahbariyat uchun."""
    survey = get_object_or_404(Survey, pk=pk)
    stored = get_object_or_404(
        ResponseFile.objects.select_related("response"),
        pk=fid,
        response__in=services.responses_for(request.user, survey),
    )
    inline = stored.inline and request.GET.get("download") != "1"
    try:
        handle = stored.file.open("rb")
    except FileNotFoundError as exc:
        raise Http404("Fayl topilmadi") from exc
    response = FileResponse(handle, as_attachment=not inline, filename=stored.name, content_type=stored.content_type)
    response["X-Content-Type-Options"] = "nosniff"
    response["Content-Security-Policy"] = "sandbox; default-src 'none'; img-src 'self'; style-src 'unsafe-inline'"
    response["Cache-Control"] = "private, max-age=600"
    return response


def _zip_part(text, fallback="—"):
    text = re.sub(r'[\\/:*?"<>|\x00-\x1f]+', " ", str(text or "")).strip(" .")
    return text[:80] or fallback


@management_required
def survey_files_zip(request, pk):
    """Fayllarni bitta ZIP'da: papkalar fakultet va talaba bo'yicha, joriy filtrlar hisobga olinadi."""
    survey = get_object_or_404(Survey, pk=pk)
    questions = list(survey.questions.filter(kind=Question.Kind.FILE))
    if request.GET.get("question", "").isdigit():
        questions = [q for q in questions if q.pk == int(request.GET["question"])]
    stored = (
        ResponseFile.objects.filter(question__in=questions, response__in=_filtered(request, survey))
        .select_related("response", "response__faculty", "question")
        .order_by("response__faculty__name", "response__full_name", "response_id", "id")
    )
    if not stored.exists():
        messages.info(request, "Tanlangan javoblarda yuklangan fayl yo'q")
        return redirect(reverse("web:survey-results", args=[survey.pk]))
    numbers = {q.pk: n for n, q in enumerate(survey.questions.exclude(kind=Question.Kind.SECTION), 1)}
    archive_file = tempfile.TemporaryFile()
    used, count = set(), 0
    with zipfile.ZipFile(archive_file, "w", zipfile.ZIP_STORED) as archive:
        for item in stored:
            answer = item.response
            folder = _zip_part(answer.faculty.short_name if answer.faculty_id else "", "Fakultetsiz")
            person = _zip_part(" ".join(filter(None, [answer.display_name, answer.group])), f"Javob {answer.pk}")
            name = _zip_part(item.name, f"fayl-{item.pk}")
            if len(questions) > 1:
                name = f"{numbers.get(item.question_id, 0)}-savol - {name}"
            path = f"{folder}/{person}/{name}"
            stem, dot, ext = path.rpartition(".")
            copy = 2
            while path in used:
                path = f"{stem} ({copy}).{ext}" if dot else f"{stem}{ext} ({copy})"
                copy += 1
            used.add(path)
            try:
                entry = zipfile.ZipInfo(path, timezone.localtime(item.created_at).timetuple()[:6])
                with item.file.open("rb") as source, archive.open(entry, "w", force_zip64=True) as target:
                    shutil.copyfileobj(source, target, 1024 * 1024)
            except FileNotFoundError:
                continue
            count += 1
    archive_file.seek(0)
    audit.record(
        AuditLog.Action.EXPORT,
        actor=request.user,
        actor_repr=request.user.username,
        actor_role="Platforma egasi" if request.user.is_superuser else request.user.get_role_display(),
        changes={
            "file": {"label": "Fayl", "new": f"So'rovnoma fayllari (ZIP): {survey.title}"[:200]},
            "count": {"label": "Fayllar soni", "new": str(count)},
        },
    )
    stamp = timezone.localtime().strftime("%Y%m%d-%H%M")
    return FileResponse(archive_file, as_attachment=True, filename=f"sorovnoma-{survey.pk}-fayllar-{stamp}.zip")


XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


@management_required
def survey_export_xlsx(request, pk):
    survey = get_object_or_404(Survey, pk=pk)
    institution = request.institution.name if request.institution else "Talent Hub"
    conditions = analytics.parse_conditions(survey, request.GET.getlist("answer"))
    content = exports.results_workbook(
        survey,
        _filtered(request, survey),
        institution=institution,
        conditions=conditions,
        faculties=_faculties_for(request.user),
        tutors=_tutors_for(request.user),
    )
    response = HttpResponse(content, content_type=XLSX)
    stamp = timezone.localtime().strftime("%Y%m%d-%H%M")
    response["Content-Disposition"] = f'attachment; filename="sorovnoma-{survey.pk}-natijalar-{stamp}.xlsx"'
    return response


@management_required
def survey_export_docx(request, pk):
    """Natijalar hisoboti Word'da: joriy filtrlar (fakultet, tyutor, javob sharti) hisobga olinadi."""
    survey = get_object_or_404(Survey, pk=pk)
    content = word_report.render(
        survey,
        _filtered(request, survey),
        institution=request.institution.name if request.institution else "Talent Hub",
        prepared_by=request.user.get_full_name() or request.user.username,
        conditions=analytics.parse_conditions(survey, request.GET.getlist("answer")),
        faculties=_faculties_for(request.user),
        tutors=_tutors_for(request.user),
    )
    response = HttpResponse(content, content_type=DOCX)
    stamp = timezone.localtime().strftime("%Y%m%d-%H%M")
    response["Content-Disposition"] = f'attachment; filename="sorovnoma-{survey.pk}-hisobot-{stamp}.docx"'
    return response


@management_required
def survey_export(request, pk):
    survey = get_object_or_404(Survey, pk=pk)
    content = services.render_csv(survey, _filtered(request, survey))
    response = HttpResponse(content, content_type="text/csv; charset=utf-8")
    stamp = timezone.localdate().strftime("%Y%m%d")
    response["Content-Disposition"] = f'attachment; filename="sorovnoma-{survey.pk}-javoblar-{stamp}.csv"'
    return response


@management_required
@require_POST
def survey_register(request, pk):
    survey = get_object_or_404(Survey, pk=pk)
    ids = [i for i in request.POST.getlist("response") if i.isdigit()]
    back = f"{reverse('web:survey-results', args=[survey.pk])}?tab=responses"
    if not ids:
        messages.error(request, "Avval talabalarni belgilang")
        return redirect(back)
    result = services.register_talents(
        survey, services.responses_for(request.user, survey).filter(pk__in=ids), by=request.user
    )
    parts = [f"Reyestrga qo'shildi: {result['added']}"]
    if result["existing"]:
        parts.append(f"oldin bor edi: {result['existing']}")
    if result["skipped"]:
        parts.append(f"platformada akkaunti yo'q: {result['skipped']}")
    messages.success(request, ", ".join(parts))
    return redirect(back)


@login_required
def survey_poster(request, pk):
    survey = get_object_or_404(Survey, pk=pk)
    tutor = _link_tutor(request)
    own = tutor is not None and tutor.user_id == request.user.pk  # tyutor o'z plakatini chop etadi
    if not (request.user.is_management or own):
        raise PermissionDenied
    context = {"survey": survey, "tutor": tutor, "share": _share(request, survey, tutor)}
    return render(request, "web/surveys/poster.html", context)


@management_required
def survey_tutor_links(request, pk):
    """Har bir tyutor uchun shaxsiy havola va QR: talaba ochganda fakultet va tyutor oldindan tanlangan bo'ladi."""
    survey = get_object_or_404(Survey, pk=pk)
    tutors = _tutors_for(request.user)
    counts = dict(
        services.responses_for(request.user, survey)
        .filter(tutor__isnull=False)
        .values("tutor")
        .annotate(n=Count("id"))
        .values_list("tutor", "n")
    )
    groups = []
    for tutor in tutors:
        share = _share(request, survey, tutor)
        item = {"tutor": tutor, "url": share["url"], "qr": share["qr"], "count": counts.get(tutor.pk, 0)}
        item["message"] = (
            f"Hurmatli talabalar! «{survey.title}» so'rovnomasini to'ldiring. Ro'yxatdan o'tish shart emas, "
            f"bir necha daqiqa vaqt oladi. Tyutoringiz: {tutor.full_name}.\n{share['url']}"
        )
        if not groups or groups[-1]["faculty"] != tutor.faculty:
            groups.append({"faculty": tutor.faculty, "items": []})
        groups[-1]["items"].append(item)
    for group in groups:
        group["text"] = "\n".join(f"{i['tutor'].full_name}: {i['url']}" for i in group["items"])
        group["silent"] = sum(1 for i in group["items"] if not i["count"])
    context = {"survey": survey, "groups": groups, "total": len(tutors), "share": _share(request, survey)}
    return render(request, "web/surveys/tutor_links.html", context)


# ---------------------------------------------------------------- ommaviy to'ldirish


def _fields(questions, data, errors):
    """Shablon uchun: har bir savol, kiritilgan qiymat va xato."""
    fields = []
    for question in questions:
        name = f"q{question.pk}"
        values = data.getlist(name) if data else []
        value = values[0] if values else ""
        known = {v for v, _ in question.choices}
        fields.append(
            {
                "q": question,
                "name": name,
                "value": value,
                "values": values,
                "other": data.get(f"{name}_other", "") if data else "",
                "other_checked": services.OTHER in values
                or (bool(value) and value not in known and question.allow_other),
                "error": errors.get(question.pk, ""),
                "choices": [(v, f"{ICONS[v]} {text}") for v, text in question.choices]
                if question.kind == Question.Kind.TRACK
                else question.choices,
            }
        )
        if question.kind == Question.Kind.FILE:
            types = question.file_types or list(file_rules.TYPES)
            fields[-1] |= {
                "accept": file_rules.accept_for(types),
                "exts": ",".join(ext for t in types for ext in file_rules.TYPES[t]["ext"]),
                "types_label": file_rules.describe(types),
            }
    return fields


def _too_large(request, questions) -> bool:
    try:
        length = int(request.META.get("CONTENT_LENGTH") or 0)
    except ValueError:
        return False
    return length > file_rules.request_limit(questions)


def _identity_initial(user):
    if not user.is_authenticated:
        return {}
    return {"full_name": user.get_full_name(), "faculty": user.faculty_id, "course": user.course}


def _missing(request):
    """Noto'g'ri, o'chirilgan yoki hali e'lon qilinmagan so'rovnoma havolasi."""
    return render(request, "web/surveys/done.html", {"survey": None, "state": "missing"}, status=404)


@never_cache  # hosting keshi xavfsizlik tokenini boshqa talabalarga bermasin
def survey_fill(request, token):
    survey = Survey.objects.filter(token=token).first()
    user = request.user
    if survey is None:
        return _missing(request)
    preview = survey.status == Survey.Status.DRAFT
    if preview and not (user.is_authenticated and user.is_management):
        return _missing(request)

    browser_key = request.COOKIES.get(BROWSER_COOKIE, "")
    state = None
    if not preview and not survey.is_accepting:
        state = "closed"
    elif not preview and services.already_answered(survey, user, browser_key):
        state = "answered"
    if state:
        context = {"survey": survey, "state": state, "share_url": _fill_url(request, survey)}
        if state == "answered":
            context["new_account"] = _waiting_account(survey, user, browser_key)
            context["login_url"] = request.build_absolute_uri(reverse("web:login"))
        return render(request, "web/surveys/done.html", context)

    questions = list(survey.questions.all())
    errors = {}
    via_tutor = _link_tutor(request) if survey.collect_identity else None
    initial = _identity_initial(user)
    if via_tutor is not None:
        initial.update(faculty=via_tutor.faculty_id, tutor=via_tutor.pk)
    identity = SurveyIdentityForm(initial=initial) if survey.collect_identity else None
    file_questions = [q for q in questions if q.kind == Question.Kind.FILE]
    if request.method == "POST" and not preview and _too_large(request, questions):
        messages.error(request, "Yuborilgan fayllar hajmi ruxsat etilganidan katta. Kichikroq fayl tanlang")
        request.method = "GET"  # tanani o'qimasdan formani qayta ko'rsatamiz
    if request.method == "POST" and not preview:
        if request.POST.get("website"):  # botlar uchun tuzoq maydon
            return redirect("web:survey-thanks", token=survey.token)
        answers, errors = services.clean_answers(survey, request.POST, questions, files=request.FILES)
        if survey.collect_identity:
            identity = SurveyIdentityForm(request.POST)
        sent = sum(len(request.FILES.getlist(f"q{q.pk}")) for q in file_questions)
        if sent and file_rules.over_ip_limit(request.META.get("REMOTE_ADDR", ""), sent):
            errors = {q.pk: "Juda ko'p fayl yuborildi. Birozdan keyin qayta urinib ko'ring" for q in file_questions}
        valid = not errors and (identity is None or identity.is_valid())
        if not valid:
            for q in file_questions:  # brauzer tanlangan faylni qayta ko'rsatmaydi: talabaga eslatamiz
                if request.FILES.getlist(f"q{q.pk}") and q.pk not in errors:
                    errors[q.pk] = "Boshqa savollarda xato bo'lgani uchun faylni qayta tanlang"
        if valid:
            try:
                saved = services.submit(
                    survey,
                    answers=answers,
                    identity=identity.cleaned_data if identity is not None else None,
                    user=user,
                    browser_key=browser_key,
                )
            except SurveyError as exc:
                messages.error(request, str(exc))
            else:
                if not user.is_authenticated and saved.user_id:
                    request.session[f"sv-account:{survey.token}"] = _account_note(saved)
                return redirect("web:survey-thanks", token=survey.token)
        else:
            messages.error(request, "Ba'zi javoblarda xato bor: belgilangan savollarni tekshiring")

    answerable = sum(1 for q in questions if q.is_answerable)
    context = {
        "survey": survey,
        "fields": _fields(questions, request.POST if request.method == "POST" else None, errors),
        "identity": identity,
        "via_tutor": via_tutor,
        "preview": preview,
        "required_count": sum(1 for q in questions if q.required),
        "answerable": answerable,
        "minutes": max(1, round(answerable * 0.4)),
        "other": services.OTHER,
    }
    response = render(request, "web/surveys/fill.html", context)
    if not browser_key:
        response.set_cookie(
            BROWSER_COOKIE, secrets.token_hex(16), max_age=BROWSER_COOKIE_AGE, httponly=True, samesite="Lax",
            secure=request.is_secure(),
        )  # fmt: skip
    return response


def survey_thanks(request, token):
    survey = Survey.objects.filter(token=token).exclude(status=Survey.Status.DRAFT).first()
    if survey is None:
        return _missing(request)
    user = request.user
    reward = (
        PointTransaction.objects.filter(user=user, reason=PointTransaction.Reason.SURVEY, ref=f"survey:{survey.pk}")
        .values_list("xp", flat=True)
        .first()
        if user.is_authenticated
        else None
    )
    xp = reward or 0
    context = {
        "survey": survey,
        "state": "thanks",
        "xp": xp,
        "share_url": _fill_url(request, survey),
        # Sessiya saqlanmagan bo'lsa ham (cookie), shu brauzerdan ochilgan akkaunt topiladi
        "new_account": request.session.pop(f"sv-account:{survey.token}", None)
        or _waiting_account(survey, user, request.COOKIES.get(BROWSER_COOKIE, "")),
        "login_url": request.build_absolute_uri(reverse("web:login")),
    }
    return render(request, "web/surveys/done.html", context)


def _waiting_account(survey, user, browser_key):
    """«Allaqachon javob bergansiz» sahifasi uchun: shu brauzerdan yuborilgan javob ochgan akkaunt.

    Talaba «Rahmat» sahifasidagi login-parolni saqlamay qolgan bo'lsa, javob bergan telefonida yana ko'radi.
    Faqat akkaunt aynan shu javob bilan ochilgan va talaba hali kirmagan bo'lsa: birinchi kirishda boshlang'ich
    parol o'chadi. Boshqa talabaning ismini yozib, uning oldin ochilgan akkauntiga bog'langan javobda parol chiqmaydi.
    """
    if user.is_authenticated or not browser_key:
        return None
    response = (
        Response.objects.filter(survey=survey, browser_key=browser_key[:32], user__isnull=False)
        .order_by("submitted_at")
        .first()
    )
    if response is None:
        return None
    account = IssuedAccount.objects.filter(user_id=response.user_id, survey=survey).select_related("user").first()
    if account is None or not account.initial_password:
        return None
    if not timedelta(0) <= account.created_at - response.submitted_at <= timedelta(minutes=1):
        return None
    return {"login": account.user.username, "password": account.initial_password}


def _account_note(response):
    """«Rahmat» sahifasi uchun: yangi ochilgan akkauntning login va boshlang'ich paroli.

    Javob oldin ochilgan akkauntga bog'langan bo'lsa parol ko'rsatilmaydi: boshqa talabaning ismini yozgan
    odam uning parolini ko'rib qolmasin.
    """
    account = getattr(response, "issued_account", None)
    if getattr(response, "account_created", False) and account is not None and account.initial_password:
        return {"login": account.user.username, "password": account.initial_password}
    return {"login": response.user.username, "existing": True}
