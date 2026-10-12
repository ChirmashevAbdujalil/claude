from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.safestring import mark_safe
from django.views.decorators.http import require_POST

from apps.ai import services as ai_services
from apps.arena.models import Streak
from apps.profiles import resume as resume_lib
from apps.profiles.models import Achievement, UserSkill
from apps.profiles.services import skill_map

from ..forms import AchievementForm, ProfileForm, ResumeForm, UserSkillForm
from .common import run_service


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


def _lang(request):
    return "en" if request.GET.get("lang", request.POST.get("lang")) == "en" else "uz"


@login_required
def resume(request):
    """Rezyume: matnlarni tahrirlash, AI bilan yozish va PDF yuklab olish."""
    user = request.user
    resume_obj = resume_lib.get_resume(user)
    form = ResumeForm(request.POST or None, instance=resume_obj, user=user)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Rezyume saqlandi")
        return redirect("web:profile-resume")
    lang = _lang(request)
    portfolio = resume_lib.portfolio_url(user, request)
    context = {
        "form": form,
        "lang": lang,
        "preview": resume_lib.collect(user, lang, portfolio_url=portfolio),
        # SVG'ni o'zimiz yasaymiz, unda foydalanuvchi kiritgan matn yo'q
        "preview_qr": mark_safe(resume_lib.qr_svg(portfolio)) if portfolio else "",
        "ai_ready": ai_services.is_configured(),
        "ai_left": ai_services.ai_resume_uses_left(user),
        "checklist": [
            ("Kamida 3 ta ko'nikma", user.skills.count() >= 3),
            ("Tasdiqlangan yutuq", user.achievements.filter(status=Achievement.Status.APPROVED).exists()),
            ("Loyihada ishtirok", user.project_memberships.filter(status="active").exists()),
            ("Ommaviy portfolio (QR kod uchun)", bool(portfolio)),
            ("Aloqa: email yoki telefon", bool(user.email or resume_obj.phone)),
        ],
    }
    return render(request, "web/profile/resume.html", context)


@login_required
@require_POST
def resume_ai(request):
    lang = _lang(request)
    if not ai_services.is_configured():
        messages.error(request, ai_services.NOT_CONFIGURED)
    elif run_service(request, ai_services.write_resume, request.user, lang):
        messages.success(request, "AI xulosani yozdi. Tekshirib, kerak bo'lsa tahrirlang ✨")
    return redirect(reverse("web:profile-resume") + f"?lang={lang}")


def _pdf_response(user, lang, public, request, inline):
    data = resume_lib.collect(user, lang, public=public, portfolio_url=resume_lib.portfolio_url(user, request))
    response = HttpResponse(resume_lib.render_pdf(data), content_type="application/pdf")
    disposition = "inline" if inline else "attachment"
    response["Content-Disposition"] = f'{disposition}; filename="{resume_lib.filename(user, lang)}"'
    return response


@login_required
def resume_pdf(request):
    return _pdf_response(request.user, _lang(request), False, request, request.GET.get("view") == "1")


def public_resume_pdf(request, slug):
    """Portfolio sahifasidan rezyume: faqat ommaviy profillar uchun, telefon va email talaba ruxsati bilan."""
    User = get_user_model()
    user = get_object_or_404(User, portfolio_slug=slug, is_active=True)
    if not user.is_public:
        raise Http404
    return _pdf_response(user, _lang(request), True, request, request.GET.get("view") == "1")
