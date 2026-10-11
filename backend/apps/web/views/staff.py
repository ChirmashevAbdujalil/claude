from django.contrib import messages
from django.contrib.auth import get_user_model
from django.db import IntegrityError
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from apps.ai import services as ai_services
from apps.discovery import services as discovery
from apps.discovery.models import Submission
from apps.insights.services import dashboard
from apps.profiles import services as profiles
from apps.profiles.models import Achievement, UserSkill
from apps.projects.models import Project

from ..forms import ReviewForm, TalentFlagForm
from .common import management_required, reviewer_required, run_service

User = get_user_model()


@reviewer_required
def review_queue(request):
    tab = request.GET.get("tab", "submissions")
    submissions = (
        Submission.objects.filter(status=Submission.Status.PENDING)
        .exclude(user=request.user)
        .select_related("challenge", "user", "user__faculty")
        .order_by("created_at")
    )
    achievements = (
        Achievement.objects.filter(status=Achievement.Status.PENDING)
        .exclude(user=request.user)
        .select_related("user", "user__faculty")
        .order_by("created_at")
    )
    context = {
        "tab": tab,
        "submissions": submissions,
        "achievements": achievements,
        "kind_xp": Achievement.DEFAULT_XP,
        "ai_ready": ai_services.is_configured(),
    }
    return render(request, "web/staff/review.html", context)


@reviewer_required
@require_POST
def review_submission(request, pk):
    submission = get_object_or_404(Submission, pk=pk)
    form = ReviewForm(request.POST)
    if form.is_valid():
        accept = request.POST.get("decision") == "accept"
        result = run_service(
            request,
            discovery.review,
            submission,
            request.user,
            accept,
            form.cleaned_data.get("score"),
            form.cleaned_data.get("feedback") or "",
        )
        if result:
            messages.success(request, f"Yechim {'qabul qilindi' if accept else 'rad etildi'}")
    return redirect(reverse("web:review") + "?tab=submissions")


@reviewer_required
@require_POST
def review_achievement(request, pk):
    achievement = get_object_or_404(Achievement, pk=pk)
    approve = request.POST.get("decision") == "approve"
    xp = request.POST.get("xp")
    result = run_service(
        request,
        profiles.review_achievement,
        achievement,
        request.user,
        approve,
        int(xp) if xp and xp.isdigit() else None,
        request.POST.get("comment", ""),
    )
    if result:
        messages.success(request, f"Yutuq {'tasdiqlandi' if approve else 'rad etildi'}")
    return redirect(reverse("web:review") + "?tab=achievements")


@reviewer_required
@require_POST
def endorse_skill(request, pk):
    user_skill = get_object_or_404(UserSkill.objects.select_related("user", "skill"), pk=pk)
    run_service(
        request,
        profiles.endorse,
        user_skill,
        request.user,
        request.POST.get("comment", ""),
        success=f"«{user_skill.skill.name}» ko'nikmasi tasdiqlandi",
    )
    return (
        redirect("web:portfolio", slug=user_skill.user.portfolio_slug)
        if user_skill.user.portfolio_slug
        else redirect("web:review")
    )


@reviewer_required
@require_POST
def talent_flag(request, user_id):
    student = get_object_or_404(User, pk=user_id, role=User.Role.STUDENT)
    form = TalentFlagForm(request.POST)
    if form.is_valid():
        flag = form.save(commit=False)
        flag.student = student
        flag.flagged_by = request.user
        try:
            flag.save()
            messages.success(request, "✨ Iqtidor belgisi qo'yildi. Rahbariyat buni ko'radi.")
        except IntegrityError:
            messages.error(request, "Siz bu yo'nalishda allaqachon belgi qo'ygansiz")
    return redirect("web:portfolio", slug=student.portfolio_slug) if student.portfolio_slug else redirect("web:review")


@management_required
def insights(request):
    data = dashboard(request.user)
    level_max = max((row["count"] for row in data["level_distribution"]), default=0)
    faculty_max = max((row["total_xp"] for row in data["by_faculty"]), default=0)
    stage_labels = dict(Project.Stage.choices)
    stages = [
        {"label": stage_labels[key], "count": data["projects_by_stage"].get(key, 0)} for key in Project.STAGE_ORDER
    ]
    return render(
        request,
        "web/staff/insights.html",
        {"data": data, "level_max": level_max, "faculty_max": faculty_max, "stages": stages},
    )


@reviewer_required
@require_POST
def review_submission_ai(request, pk):
    """AI'dan baho va izoh qoralamasini so'raydi. O'qituvchi uni tekshirib, tasdiqlaydi yoki o'zgartiradi."""
    submission = get_object_or_404(Submission.objects.select_related("challenge"), pk=pk)
    if submission.status != Submission.Status.PENDING:
        messages.error(request, "Bu yechim allaqachon tekshirilgan")
    elif run_service(request, ai_services.suggest_review, submission):
        messages.success(request, "AI taklifi tayyor: baho va izohni tekshirib, tasdiqlang")
    return redirect(reverse("web:review") + f"?tab=submissions#submission-{pk}")
