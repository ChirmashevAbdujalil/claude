"""So'rovnomalar: konstruktor, ommaviy to'ldirish sahifasi, natijalar, eksport va iqtidorlar reyestriga qo'shish."""

import json
import secrets

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import Q
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.accounts.models import Faculty
from apps.arena.models import PointTransaction
from apps.surveys import services
from apps.surveys.models import Question, Response, Survey
from apps.surveys.services import SurveyError

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


def _share(request, survey):
    url = request.build_absolute_uri(reverse("web:survey-fill", args=[survey.token]))
    return {"url": url, "qr": qr_svg(url, label=f"«{survey.title}» so'rovnomasining QR kodi")}


def _filtered(request, survey):
    responses = services.responses_for(request.user, survey)
    params = request.GET
    if params.get("faculty", "").isdigit():
        responses = responses.filter(faculty_id=params["faculty"])
    if params.get("course", "").isdigit():
        responses = responses.filter(course=params["course"])
    if params.get("q"):
        q = params["q"].strip()
        responses = responses.filter(
            Q(full_name__icontains=q) | Q(user__username__icontains=q) | Q(group__icontains=q) | Q(phone__icontains=q)
        )
    if params.get("linked") == "1":
        responses = responses.filter(user__isnull=False)
    return responses


def _filter_qs(request):
    query = request.GET.copy()
    for key in ("tab", "page"):
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
    context = {
        "survey": survey,
        "tab": tab,
        "filters": request.GET,
        "filter_qs": _filter_qs(request),
        "faculties": Faculty.objects.order_by("name"),
        "courses": range(1, 7),
        "can_edit": services.can_edit(request.user, survey),
        "share": _share(request, survey),
        "summary": services.summary(survey, responses),
        "has_track": survey.questions.filter(kind=Question.Kind.TRACK).exists(),
    }
    if tab == "responses":
        page = paginate(request, responses, per_page=30)
        registered = services.in_registry(page.object_list)
        for response in page.object_list:
            response.in_registry = response.user_id in registered
        context["page"] = page
    return render(request, "web/surveys/results.html", context)


@management_required
def survey_response(request, pk, rid):
    survey = get_object_or_404(Survey, pk=pk)
    response = get_object_or_404(services.responses_for(request.user, survey), pk=rid)
    context = {
        "survey": survey,
        "response": response,
        "rows": services.answer_rows(survey, response),
        "in_registry": bool(response.user_id and services.in_registry([response])),
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


@management_required
def survey_poster(request, pk):
    survey = get_object_or_404(Survey, pk=pk)
    return render(request, "web/surveys/poster.html", {"survey": survey, "share": _share(request, survey)})


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
                "choices": question.choices,
            }
        )
    return fields


def _identity_initial(user):
    if not user.is_authenticated:
        return {}
    return {"full_name": user.get_full_name(), "faculty": user.faculty_id, "course": user.course}


def survey_fill(request, token):
    survey = Survey.objects.filter(token=token).first()
    if survey is None:
        raise Http404
    user = request.user
    preview = survey.status == Survey.Status.DRAFT
    if preview and not (user.is_authenticated and user.is_management):
        raise Http404
    if survey.access == Survey.Access.STUDENTS and not user.is_authenticated:
        return redirect_to_login(request.get_full_path(), reverse("web:login"))

    browser_key = request.COOKIES.get(BROWSER_COOKIE, "")
    state = None
    if not preview and not survey.is_accepting:
        state = "closed"
    elif not preview and services.already_answered(survey, user, browser_key):
        state = "answered"
    if state:
        return render(request, "web/surveys/done.html", {"survey": survey, "state": state})

    questions = list(survey.questions.all())
    errors = {}
    identity = SurveyIdentityForm(initial=_identity_initial(user)) if survey.collect_identity else None
    if request.method == "POST" and not preview:
        if request.POST.get("website"):  # botlar uchun tuzoq maydon
            return redirect("web:survey-thanks", token=survey.token)
        answers, errors = services.clean_answers(survey, request.POST, questions)
        if survey.collect_identity:
            identity = SurveyIdentityForm(request.POST)
        if not errors and (identity is None or identity.is_valid()):
            try:
                services.submit(
                    survey,
                    answers=answers,
                    identity=identity.cleaned_data if identity is not None else None,
                    user=user,
                    browser_key=browser_key,
                )
            except SurveyError as exc:
                messages.error(request, str(exc))
            else:
                return redirect("web:survey-thanks", token=survey.token)
        else:
            messages.error(request, "Ba'zi javoblarda xato bor: belgilangan savollarni tekshiring")

    context = {
        "survey": survey,
        "fields": _fields(questions, request.POST if request.method == "POST" else None, errors),
        "identity": identity,
        "preview": preview,
        "required_count": sum(1 for q in questions if q.required),
        "answerable": sum(1 for q in questions if q.is_answerable),
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
        raise Http404
    user = request.user
    reward = (
        PointTransaction.objects.filter(user=user, reason=PointTransaction.Reason.SURVEY, ref=f"survey:{survey.pk}")
        .values_list("xp", flat=True)
        .first()
        if user.is_authenticated
        else None
    )
    xp = reward or 0
    return render(request, "web/surveys/done.html", {"survey": survey, "state": "thanks", "xp": xp})
