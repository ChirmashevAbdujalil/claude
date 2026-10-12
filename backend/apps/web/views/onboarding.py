from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model, login
from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.text import slugify
from django.views.decorators.http import require_POST

from apps.arena import services as arena
from apps.arena.levels import LEVELS
from apps.arena.models import Badge
from apps.discovery.models import Challenge
from apps.discovery.selectors import visible_challenges
from apps.notifications.models import Notification
from apps.notifications.services import mark_all_read
from apps.profiles.models import Achievement, Skill, UserSkill
from apps.profiles.services import ENDORSEMENT_XP
from apps.projects.services import STAGE_XP
from apps.tenants import services as tenant_services
from apps.tenants.context import unscoped

from ..forms import OnboardingProfileForm, RegisterForm
from ..guidance import next_steps

User = get_user_model()
MAX_ONBOARDING_SKILLS = 8


def register(request):
    is_open, reason = tenant_services.registration_state(request.institution)
    if not is_open and reason != "limit":
        raise Http404
    if request.user.is_authenticated:
        return redirect("web:dashboard")
    if not is_open:
        return render(request, "web/auth/register_limit.html", status=403)
    form = RegisterForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        login(request, user, backend="django.contrib.auth.backends.ModelBackend")
        messages.success(request, f"Xush kelibsiz, {user.first_name}! Keling, profilingizni sozlaymiz.")
        return redirect("web:welcome")
    return render(request, "web/auth/register.html", {"form": form})


def _unique_slug(user) -> str:
    base = slugify(f"{user.first_name}-{user.last_name}") or slugify(user.username) or "talaba"
    slug = base
    with unscoped():  # portfolio manzili butun platforma bo'yicha noyob
        taken = User.objects.filter(portfolio_slug=slug).exclude(pk=user.pk).exists()
    if taken:
        slug = f"{base}-{user.pk}"
    return slug


def _finish(user):
    if user.onboarded_at is None:
        user.onboarded_at = timezone.now()
        user.save(update_fields=["onboarded_at"])
        arena.grant_badge(user, "welcome")


@login_required
def welcome(request):
    """Boshlang'ich sozlash: 1) fakultet va kurs, 2) ko'nikmalar, 3) birinchi qadam."""
    user = request.user
    step = request.GET.get("step", "1")
    if step not in {"1", "2", "3"}:
        step = "1"

    if step == "1":
        form = OnboardingProfileForm(request.POST or None, instance=user)
        if request.method == "POST" and form.is_valid():
            user = form.save(commit=False)
            if not user.portfolio_slug:
                user.portfolio_slug = _unique_slug(user)
            user.save()
            return redirect(f"{request.path}?step=2")
        return render(request, "web/onboarding/welcome.html", {"step": 1, "form": form})

    if step == "2":
        if request.method == "POST":
            chosen = Skill.objects.filter(pk__in=request.POST.getlist("skills")[:MAX_ONBOARDING_SKILLS])
            for skill in chosen:
                UserSkill.objects.get_or_create(user=user, skill=skill, defaults={"level": 2})
            return redirect(f"{request.path}?step=3")
        mine = set(UserSkill.objects.filter(user=user).values_list("skill_id", flat=True))
        groups = []
        for value, label in Skill.Category.choices:
            skills = [s for s in Skill.objects.filter(category=value)]
            if skills:
                groups.append({"label": label, "skills": skills})
        return render(
            request,
            "web/onboarding/welcome.html",
            {"step": 2, "groups": groups, "mine": mine, "max_skills": MAX_ONBOARDING_SKILLS},
        )

    _finish(user)
    daily = (
        visible_challenges(user)
        .filter(kind=Challenge.Kind.DAILY, is_published=True, starts_at__lte=timezone.now())
        .exclude(submissions__user=user)
        .first()
    )
    return render(request, "web/onboarding/welcome.html", {"step": 3, "daily": daily, "steps": next_steps(user)})


@login_required
@require_POST
def welcome_skip(request):
    _finish(request.user)
    return redirect("web:dashboard")


def how_it_works(request):
    """Ball iqtisodiyoti qoidalari: qiymatlar to'g'ridan-to'g'ri koddagi konstantalardan olinadi."""
    kinds = dict(Challenge.Kind.choices)
    achievement_kinds = dict(Achievement.Kind.choices)
    rows = [
        ("🎯", f"{kinds[k]} challenge", f"{xp} XP", "O'qituvchi bahosiga qarab: 80 baho = 80%")
        for k, xp in Challenge.DEFAULT_XP.items()
    ]
    rows += [
        ("🎓", "O'qituvchi ko'nikmangizni tasdiqlasa", f"{ENDORSEMENT_XP} XP", "Har bir tasdiq uchun"),
        ("📅", "Tadbirda qatnashish (QR check-in)", "odatda 20 XP", "Tadbirga qarab"),
        ("🚀", "Loyiha keyingi bosqichga o'tsa", f"{STAGE_XP} XP", "Jamoaning har bir a'zosiga"),
        ("🔥", f"Har {arena.STREAK_BONUS_EVERY} kunlik streak", f"{arena.STREAK_BONUS_XP} XP", "Ketma-ket faollik"),
    ]
    achievement_rows = sorted(
        ((achievement_kinds[k], xp) for k, xp in Achievement.DEFAULT_XP.items()), key=lambda r: -r[1]
    )
    return render(
        request,
        "web/how_it_works.html",
        {
            "rows": rows,
            "achievement_rows": achievement_rows,
            "levels": LEVELS,
            "badges": Badge.objects.order_by("-xp_bonus", "name"),
            "coins_per_10": round(arena.COINS_PER_XP * 10),
            "daily_cap": settings.ARENA_DAILY_XP_CAP,
        },
    )


@login_required
def notifications(request):
    items = list(Notification.objects.filter(user=request.user)[:50])
    mark_all_read(request.user)
    return render(request, "web/notifications.html", {"items": items})


@login_required
def notification_go(request, pk):
    item = get_object_or_404(Notification, pk=pk, user=request.user)
    if not item.is_read:
        item.is_read = True
        item.save(update_fields=["is_read"])
    return redirect(item.url if item.url.startswith("/") and not item.url.startswith("//") else "web:notifications")
