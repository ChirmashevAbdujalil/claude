from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.arena.models import Streak
from apps.profiles.models import Achievement, UserSkill
from apps.profiles.services import skill_map

from ..forms import AchievementForm, ProfileForm, UserSkillForm


@login_required
def my_profile(request):
    user = request.user
    context = {
        "skill_map": skill_map(user),
        "skills": UserSkill.objects.filter(user=user).select_related("skill").prefetch_related("endorsements"),
        "achievements": Achievement.objects.filter(user=user),
        "badges": user.badges.select_related("badge"),
        "streak": Streak.objects.filter(user=user).first(),
        "skill_form": UserSkillForm(user=user),
        "memberships": user.project_memberships.select_related("project"),
    }
    return render(request, "web/profile/me.html", context)


@login_required
def edit_profile(request):
    form = ProfileForm(request.POST or None, request.FILES or None, instance=request.user)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Profil yangilandi")
        return redirect("web:profile")
    return render(request, "web/profile/edit.html", {"form": form})


@login_required
@require_POST
def add_skill(request):
    form = UserSkillForm(request.POST, user=request.user)
    if form.is_valid():
        skill = form.save(commit=False)
        skill.user = request.user
        skill.save()
        messages.success(request, f"«{skill.skill.name}» ko'nikmasi qo'shildi")
    else:
        messages.error(request, "Ko'nikmani tanlang")
    return redirect("web:profile")


@login_required
@require_POST
def remove_skill(request, pk):
    get_object_or_404(UserSkill, pk=pk, user=request.user).delete()
    messages.info(request, "Ko'nikma olib tashlandi")
    return redirect("web:profile")


@login_required
def add_achievement(request):
    form = AchievementForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        achievement = form.save(commit=False)
        achievement.user = request.user
        achievement.save()
        messages.success(request, "Yutuq yuborildi. O'qituvchi tasdiqlagach XP olasiz.")
        return redirect("web:profile")
    return render(request, "web/profile/achievement_form.html", {"form": form})


@login_required
@require_POST
def delete_achievement(request, pk):
    achievement = get_object_or_404(Achievement, pk=pk, user=request.user, status=Achievement.Status.PENDING)
    achievement.delete()
    messages.info(request, "Yutuq o'chirildi")
    return redirect("web:profile")
