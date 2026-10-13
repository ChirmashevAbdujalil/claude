"""Iqtidorli talabalar bilan ishlash: reyestr, mentor, rivojlanish rejasi, diagnostika va hisobot."""

from datetime import datetime

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.accounts.models import Faculty
from apps.opportunities.models import Opportunity
from apps.talent import diagnostics, services
from apps.talent import report as talent_report
from apps.talent.models import DevelopmentGoal, DiagnosticResult, TalentProfile
from apps.talent.tracks import DESCRIPTIONS, FIRST_STEPS, ICONS, Track, label

from ..forms import GoalForm, StudentGoalForm, TalentAddForm, TalentMentorForm, TalentProfileForm
from .common import management_required, paginate, reviewer_required

User = get_user_model()


def _profile_for(request, pk):
    profile = get_object_or_404(TalentProfile.objects.select_related("student", "student__faculty", "mentor"), pk=pk)
    if not services.can_view(request.user, profile):
        raise PermissionDenied
    return profile


def _pipeline(profile):
    steps = []
    for index, status in enumerate(TalentProfile.PIPELINE, start=1):
        state = "done" if index < profile.stage else "current" if index == profile.stage else "todo"
        if profile.status == TalentProfile.Status.ACHIEVED and index == profile.stage:
            state = "done"
        steps.append({"label": status.label, "state": state})
    return steps


# ---------------------------------------------------------------- reyestr


@management_required
def registry(request):
    params = request.GET
    profiles = services.registry(request.user, include_archived=params.get("status") == "archived")
    counts = {s: profiles.filter(status=s).count() for s in TalentProfile.PIPELINE}
    unattended = profiles.filter(mentor__isnull=True).count()
    if params.get("q"):
        q = params["q"].strip()
        profiles = profiles.filter(
            Q(student__first_name__icontains=q) | Q(student__last_name__icontains=q) | Q(student__username__icontains=q)
        )
    if params.get("status") in TalentProfile.Status.values:
        profiles = profiles.filter(status=params["status"])
    if params.get("track") in Track.values:
        profiles = profiles.filter(track=params["track"])
    if params.get("faculty", "").isdigit():
        profiles = profiles.filter(student__faculty_id=params["faculty"])
    if params.get("mentor") == "none":
        profiles = profiles.filter(mentor__isnull=True)
    page = paginate(request, profiles.order_by("status", "-created_at"), per_page=30)
    faculties = Faculty.objects.all()
    if request.user.role == User.Role.DEAN and request.user.faculty_id:
        faculties = faculties.filter(pk=request.user.faculty_id)
    context = {
        "page": page,
        "counts": [{"status": s, "label": s.label, "count": counts[s]} for s in TalentProfile.PIPELINE],
        "total": sum(counts.values()),
        "unattended": unattended,
        "suggestions": services.suggestions(request.user),
        "add_form": TalentAddForm(),
        "tracks": Track.choices,
        "statuses": TalentProfile.Status.choices,
        "faculties": faculties,
        "filters": params,
        "icons": ICONS,
    }
    return render(request, "web/talent/registry.html", context)


@management_required
@require_POST
def registry_add(request):
    student = None
    source = TalentProfile.Source.MANUAL
    if request.POST.get("student_id", "").isdigit():
        student = User.objects.filter(pk=request.POST["student_id"], role=User.Role.STUDENT).first()
        if request.POST.get("source") in TalentProfile.Source.values:
            source = request.POST["source"]
    form = TalentAddForm(request.POST)
    if student is None and form.is_valid():
        student = User.objects.filter(username=form.cleaned_data["username"].strip(), role=User.Role.STUDENT).first()
        if student is None:
            messages.error(request, "Bunday loginli talaba topilmadi")
            return redirect("web:talent-registry")
    if student is None:
        messages.error(request, "Talabani tanlang")
        return redirect("web:talent-registry")
    if (
        request.user.role == User.Role.DEAN
        and request.user.faculty_id
        and student.faculty_id != request.user.faculty_id
    ):
        raise PermissionDenied
    track = request.POST.get("track", "") if request.POST.get("track") in Track.values else ""
    note = request.POST.get("note", "").strip()[:500]
    profile, created = services.ensure_profile(student, source=source, track=track, by=request.user, note=note)
    messages.success(request, f"{student} reyestrga qo'shildi" if created else f"{student} reyestrda bor edi")
    return redirect("web:talent-profile", pk=profile.pk)


@login_required
def profile_detail(request, pk):
    profile = _profile_for(request, pk)
    user = request.user
    can_manage = services.can_manage(user, profile)
    can_plan = services.can_plan(user, profile)
    is_student = profile.student_id == user.pk
    goals = list(profile.goals.all())
    for goal in goals:
        if can_plan:
            goal.form = GoalForm(instance=goal, prefix=f"g{goal.pk}")
        elif is_student and goal.is_open:
            goal.form = StudentGoalForm(instance=goal, prefix=f"g{goal.pk}")
    diagnostic = DiagnosticResult.objects.filter(user=profile.student).first()
    context = {
        "profile": profile,
        "student": profile.student,
        "pipeline": _pipeline(profile),
        "goals": goals,
        "goal_form": GoalForm(initial={"due_date": timezone.localdate() + timezone.timedelta(days=30)})
        if can_plan
        else None,
        "mentor_form": TalentMentorForm(
            initial={"mentor": profile.mentor}, mentors=services.mentors_for(profile.student)
        )
        if can_manage
        else None,
        "profile_form": TalentProfileForm(instance=profile) if can_manage else None,
        "can_manage": can_manage,
        "can_plan": can_plan,
        "diagnostic": diagnostic,
        "ranked": [(t, label(t), ICONS[t], s) for t, s in diagnostic.ranked()] if diagnostic else [],
        "results": services.results([profile.student_id]),
        "matches": _matching_opportunities(profile.student)[:4],
        "skills": profile.student.skills.select_related("skill").order_by("-level")[:8],
        "track_icon": ICONS.get(profile.track, "✨"),
    }
    return render(request, "web/talent/profile.html", context)


@login_required
@require_POST
def profile_mentor(request, pk):
    profile = _profile_for(request, pk)
    if not services.can_manage(request.user, profile):
        raise PermissionDenied
    form = TalentMentorForm(request.POST, mentors=services.mentors_for(profile.student))
    if form.is_valid():
        try:
            services.assign_mentor(profile, form.cleaned_data["mentor"], by=request.user)
        except services.TalentError as exc:
            messages.error(request, str(exc))
        else:
            mentor = form.cleaned_data["mentor"]
            messages.success(request, f"Mentor biriktirildi: {mentor}" if mentor else "Mentor olib tashlandi")
    return redirect("web:talent-profile", pk=profile.pk)


@login_required
@require_POST
def profile_update(request, pk):
    profile = _profile_for(request, pk)
    if not services.can_manage(request.user, profile):
        raise PermissionDenied
    if request.POST.get("archive"):
        profile.status = (
            TalentProfile.Status.IDENTIFIED
            if profile.status == TalentProfile.Status.ARCHIVED
            else TalentProfile.Status.ARCHIVED
        )
        profile.save(update_fields=["status", "updated_at"])
        services.refresh_status(profile)
        messages.success(request, "Reyestrga qaytarildi" if profile.status != "archived" else "Arxivga o'tkazildi")
        return redirect("web:talent-profile", pk=profile.pk)
    form = TalentProfileForm(request.POST, instance=profile)
    if form.is_valid():
        form.save()
        messages.success(request, "Saqlandi")
    return redirect("web:talent-profile", pk=profile.pk)


# ---------------------------------------------------------------- reja


@login_required
@require_POST
def goal_create(request, pk):
    profile = _profile_for(request, pk)
    if not services.can_plan(request.user, profile):
        raise PermissionDenied
    form = GoalForm(request.POST)
    if form.is_valid():
        goal = form.save(commit=False)
        goal.profile = profile
        services.save_goal(goal, by=request.user)
        if profile.student_id != request.user.pk:
            from apps.notifications.services import notify

            notify(profile.student, f"Rejangizga yangi maqsad qo'shildi: {goal.title}",
                   f"Muddat: {goal.due_date:%d.%m.%Y}", url="/mening-yolim/", icon="🎯")  # fmt: skip
        messages.success(request, "Maqsad rejaga qo'shildi")
    else:
        messages.error(
            request, "Maqsadni saqlab bo'lmadi: " + "; ".join(e for errs in form.errors.values() for e in errs)
        )
    return redirect("web:talent-profile", pk=profile.pk)


@login_required
@require_POST
def goal_update(request, pk):
    goal = get_object_or_404(DevelopmentGoal.objects.select_related("profile", "profile__student"), pk=pk)
    profile = goal.profile
    if not services.can_view(request.user, profile):
        raise PermissionDenied
    prefix = f"g{goal.pk}"
    if services.can_plan(request.user, profile):
        form = GoalForm(request.POST, instance=goal, prefix=prefix)
    elif profile.student_id == request.user.pk and goal.is_open:
        form = StudentGoalForm(request.POST, instance=goal, prefix=prefix)
    else:
        raise PermissionDenied
    if form.is_valid():
        services.save_goal(form.save(commit=False), by=request.user)
        if isinstance(form, StudentGoalForm) and profile.mentor:
            from apps.notifications.services import notify

            notify(profile.mentor, f"{profile.student} maqsadini yangiladi: {goal.title}",
                   f"{goal.get_status_display()} · {goal.progress}%",
                   url=f"/iqtidorlar/{profile.pk}/", icon="📈")  # fmt: skip
        messages.success(request, "Maqsad yangilandi")
    else:
        messages.error(request, "Ma'lumot noto'g'ri")
    target = request.POST.get("next")
    return redirect(target if target == "/mening-yolim/" else f"/iqtidorlar/{profile.pk}/#maqsad-{goal.pk}")


@login_required
@require_POST
def goal_delete(request, pk):
    goal = get_object_or_404(DevelopmentGoal.objects.select_related("profile"), pk=pk)
    if not services.can_plan(request.user, goal.profile):
        raise PermissionDenied
    profile_pk = goal.profile_id
    goal.delete()
    messages.success(request, "Maqsad o'chirildi")
    return redirect("web:talent-profile", pk=profile_pk)


# ---------------------------------------------------------------- mentor


@reviewer_required
def mentees(request):
    profiles = list(
        services.registry(request.user)
        .filter(mentor=request.user)
        .prefetch_related("goals")
        .order_by("student__last_name")
    )
    today = timezone.localdate()
    for profile in profiles:
        open_goals = [g for g in profile.goals.all() if g.is_open]
        profile.next_goal = min(open_goals, key=lambda g: g.due_date, default=None)
        profile.overdue = [g for g in open_goals if g.due_date < today]
    context = {
        "profiles": profiles,
        "overdue_total": sum(len(p.overdue) for p in profiles),
        "no_plan": sum(1 for p in profiles if not p.goals_total),
    }
    return render(request, "web/talent/mentees.html", context)


# ---------------------------------------------------------------- talaba


def _matching_opportunities(user):
    tracks = services.user_tracks(user)
    if not tracks:
        return []
    now = timezone.now()
    visible = Opportunity.objects.filter(is_active=True).filter(Q(deadline__isnull=True) | Q(deadline__gte=now))
    return [o for o in visible.order_by("deadline", "-created_at")[:50] if tracks & set(services.opportunity_tracks(o))]


@login_required
def my_path(request):
    user = request.user
    diagnostic = DiagnosticResult.objects.filter(user=user).first()
    profile = TalentProfile.objects.filter(student=user).select_related("mentor").first()
    goals = list(profile.goals.exclude(status=DevelopmentGoal.Status.CANCELLED)) if profile else []
    for goal in goals:
        if goal.is_open:
            goal.form = StudentGoalForm(instance=goal, prefix=f"g{goal.pk}")
    track = (profile.track if profile and profile.track else None) or (diagnostic.track if diagnostic else None)
    context = {
        "diagnostic": diagnostic,
        "profile": profile,
        "pipeline": _pipeline(profile) if profile else None,
        "goals": goals,
        "track": track,
        "track_label": label(track) if track else "",
        "track_icon": ICONS.get(track, "✨"),
        "track_description": DESCRIPTIONS.get(track, ""),
        "first_steps": FIRST_STEPS.get(track, []),
        "ranked": [(t, label(t), ICONS[t], s) for t, s in diagnostic.ranked()] if diagnostic else [],
        "matches": _matching_opportunities(user)[:6],
        "done": sum(1 for g in goals if g.status == DevelopmentGoal.Status.DONE),
    }
    return render(request, "web/talent/my_path.html", context)


@login_required
def diagnostic(request):
    if request.user.role != User.Role.STUDENT:
        messages.info(request, "Diagnostika talabalar uchun")
        return redirect("web:dashboard")
    previous = DiagnosticResult.objects.filter(user=request.user).first()
    answers = dict(request.POST.items()) if request.method == "POST" else (previous.answers if previous else {})
    error = ""
    if request.method == "POST":
        try:
            result = services.save_diagnostic(request.user, answers)
        except ValueError as exc:
            error = str(exc)
        else:
            messages.success(request, f"Yo'nalishingiz aniqlandi: {ICONS[result.track]} {result.get_track_display()}")
            return redirect("web:my-path")
    questions = [
        {"key": key, "text": text, "options": [(opt, opt_text) for opt, opt_text, _ in options]}
        for key, text, options in diagnostics.QUESTIONS
    ]
    return render(request, "web/talent/diagnostic.html", {"questions": questions, "answers": answers, "error": error})


# ---------------------------------------------------------------- hisobot


def _period(request):
    start, end = services.semester_bounds()
    for key in ("from", "to"):
        try:
            value = datetime.strptime(request.GET.get(key, ""), "%Y-%m-%d").date()
        except ValueError:
            continue
        if key == "from":
            start = value
        else:
            end = value
    return start, end


@management_required
def report(request):
    start, end = _period(request)
    data = services.report(request.user, start, end)
    fmt = request.GET.get("format")
    stamp = f"{start:%Y%m%d}-{end:%Y%m%d}"
    if fmt == "pdf":
        response = HttpResponse(talent_report.render_pdf(data, request.institution), content_type="application/pdf")
        response["Content-Disposition"] = f'attachment; filename="iqtidorlar-hisoboti-{stamp}.pdf"'
        return response
    if fmt == "csv":
        response = HttpResponse(talent_report.render_csv(data), content_type="text/csv; charset=utf-8")
        response["Content-Disposition"] = f'attachment; filename="iqtidorlar-hisoboti-{stamp}.csv"'
        return response
    query = f"from={start:%Y-%m-%d}&to={end:%Y-%m-%d}"
    return render(request, "web/talent/report.html", {"data": data, "query": query})
