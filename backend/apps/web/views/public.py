from django.conf import settings
from django.contrib import messages
from django.contrib.auth import authenticate, get_user_model, login, logout
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from apps.accounts.telegram import TelegramAuthError, verify_init_data
from apps.arena.levels import LEVELS
from apps.discovery.models import Challenge, TalentFlag
from apps.opportunities import services as opportunity_services
from apps.opportunities.models import Sponsor
from apps.profiles.models import Achievement, UserSkill
from apps.profiles.services import skill_map
from apps.projects.models import Project

from ..forms import LoginForm, TalentFlagForm

User = get_user_model()


def _safe_next(request, fallback="web:dashboard"):
    target = request.POST.get("next") or request.GET.get("next")
    if target and url_has_allowed_host_and_scheme(target, {request.get_host()}, request.is_secure()):
        return target
    return fallback


def landing(request):
    if request.user.is_authenticated:
        return redirect("web:dashboard")
    stats = {
        "students": User.objects.filter(role=User.Role.STUDENT).count(),
        "challenges": Challenge.objects.filter(is_published=True).count(),
        "projects": Project.objects.count(),
        "achievements": Achievement.objects.filter(status=Achievement.Status.APPROVED).count(),
    }
    sponsors = Sponsor.objects.filter(is_active=True)
    return render(request, "web/landing.html", {"stats": stats, "levels": LEVELS, "sponsors": sponsors})


def login_view(request):
    if request.user.is_authenticated:
        return redirect(_safe_next(request))
    form = LoginForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = authenticate(request, **form.cleaned_data)
        if user is None:
            form.add_error(None, "Login yoki parol noto'g'ri")
        else:
            login(request, user)
            messages.success(request, f"Xush kelibsiz, {user.first_name or user.username}!")
            return redirect(_safe_next(request))
    return render(request, "web/auth/login.html", {"form": form, "next": request.GET.get("next", "")})


@require_POST
def logout_view(request):
    logout(request)
    return redirect("web:landing")


@require_POST
def telegram_login(request):
    """Telegram Mini App ichida avtomatik kirish (initData imzosi tekshiriladi)."""
    try:
        tg_user = verify_init_data(
            request.POST.get("init_data", ""), settings.TELEGRAM_BOT_TOKEN, settings.TELEGRAM_AUTH_MAX_AGE
        )
    except TelegramAuthError as exc:
        return JsonResponse({"detail": str(exc)}, status=401)
    with transaction.atomic():
        user, created = User.objects.get_or_create(
            telegram_id=tg_user["id"],
            defaults={
                "username": f"tg{tg_user['id']}",
                "first_name": tg_user.get("first_name", "")[:150],
                "last_name": tg_user.get("last_name", "")[:150],
            },
        )
        if created:
            user.set_unusable_password()
            user.save(update_fields=["password"])
    if not user.is_active:
        return JsonResponse({"detail": "Hisob bloklangan"}, status=403)
    login(request, user, backend="django.contrib.auth.backends.ModelBackend")
    return JsonResponse({"created": created})


def portfolio(request, slug):
    profile = get_object_or_404(User.objects.select_related("faculty"), portfolio_slug=slug, is_active=True)
    is_owner = request.user.is_authenticated and request.user.pk == profile.pk
    is_reviewer = request.user.is_authenticated and request.user.is_reviewer
    if not profile.is_public and not (is_owner or is_reviewer):
        return render(request, "web/404.html", status=404)

    skills = UserSkill.objects.filter(user=profile).select_related("skill").prefetch_related("endorsements")
    endorsed_ids = set()
    if is_reviewer:
        endorsed_ids = set(
            UserSkill.objects.filter(user=profile, endorsements__endorsed_by=request.user).values_list("id", flat=True)
        )
    context = {
        "profile": profile,
        "is_owner": is_owner,
        "is_reviewer": is_reviewer and not is_owner,
        "skill_map": skill_map(profile),
        "skills": skills,
        "endorsed_ids": endorsed_ids,
        "achievements": Achievement.objects.filter(user=profile, status=Achievement.Status.APPROVED),
        "badges": profile.badges.select_related("badge"),
        "projects": profile.project_memberships.filter(status="active").select_related("project"),
        "flag_form": TalentFlagForm() if is_reviewer and not is_owner else None,
        "flags": TalentFlag.objects.filter(student=profile).select_related("flagged_by") if is_reviewer else [],
        "share_url": request.build_absolute_uri(),
    }
    return render(request, "web/profile/portfolio.html", context)


@login_required
def menu(request):
    return render(request, "web/menu.html")


def page_not_found(request, exception=None):
    return render(request, "web/404.html", status=404)


def _contact_url(contact: str) -> str:
    """SPONSOR_CONTACT dan havola yasaydi: email, @telegram yoki to'liq URL."""
    contact = contact.strip()
    if not contact:
        return ""
    if contact.startswith(("http://", "https://")):
        return contact
    if contact.startswith("@"):
        return f"https://t.me/{contact[1:]}"
    if "@" in contact:
        return f"mailto:{contact}"
    return ""


def sponsors(request):
    contact = settings.SPONSOR_CONTACT
    context = {
        "sponsors": opportunity_services.active_sponsors(),
        "totals": opportunity_services.sponsor_totals(),
        "contact": contact,
        "contact_url": _contact_url(contact),
    }
    return render(request, "web/sponsors.html", context)
