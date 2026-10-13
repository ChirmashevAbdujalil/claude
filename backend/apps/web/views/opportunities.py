from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.arena.levels import level_for_xp
from apps.opportunities import services
from apps.opportunities.models import Application, Opportunity, Redemption, Reward, Sponsor
from apps.talent import services as talent_services

from ..forms import ApplyForm, OpportunityForm
from .common import paginate, run_service

KINDS = [("", "Barchasi")] + list(Opportunity.Kind.choices)


def _can_publish(user):
    return user.is_management or user.role == user.Role.PARTNER


def _visible(user):
    if user.is_management:
        return Opportunity.objects.all()
    active = Opportunity.objects.filter(is_active=True).filter(
        Q(deadline__isnull=True) | Q(deadline__gte=timezone.now())
    )
    if user.role == user.Role.PARTNER:
        return Opportunity.objects.filter(Q(pk__in=active.values("pk")) | Q(created_by=user))
    return active


@login_required
def opportunity_list(request):
    kind = request.GET.get("kind", "")
    opportunities = _visible(request.user)
    if kind:
        opportunities = opportunities.filter(kind=kind)
    applied = set(Application.objects.filter(user=request.user).values_list("opportunity_id", flat=True))
    page = paginate(request, opportunities.order_by("deadline", "-created_at"))
    my_level = level_for_xp(request.user.xp)["number"]
    my_tracks = talent_services.user_tracks(request.user)
    for item in page:
        item.applied = item.pk in applied
        item.locked = item.min_level > my_level
        item.matches = bool(my_tracks & set(talent_services.opportunity_tracks(item)))
    return render(
        request,
        "web/opportunities/list.html",
        {"page": page, "kinds": KINDS, "kind": kind, "can_publish": _can_publish(request.user)},
    )


@login_required
def opportunity_detail(request, pk):
    opportunity = get_object_or_404(_visible(request.user), pk=pk)
    application = Application.objects.filter(opportunity=opportunity, user=request.user).first()
    form = ApplyForm(request.POST or None)
    if request.method == "POST" and application is None and form.is_valid():
        result = run_service(
            request,
            services.apply,
            opportunity,
            request.user,
            form.cleaned_data["motivation"],
            success="Ariza yuborildi! Omad tilaymiz 🍀",
        )
        if result:
            return redirect("web:opportunity-detail", pk=pk)
    can_manage = request.user.is_management or opportunity.created_by_id == request.user.id
    context = {
        "opportunity": opportunity,
        "application": application,
        "form": form,
        "locked": opportunity.min_level > level_for_xp(request.user.xp)["number"],
        "applications": opportunity.applications.select_related("user") if can_manage else None,
    }
    return render(request, "web/opportunities/detail.html", context)


@login_required
def opportunity_form(request):
    if not _can_publish(request.user):
        raise PermissionDenied
    form = OpportunityForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        opportunity = form.save(commit=False)
        opportunity.created_by = request.user
        opportunity.save()
        messages.success(request, "Imkoniyat e'lon qilindi")
        return redirect("web:opportunity-detail", pk=opportunity.pk)
    return render(request, "web/opportunities/form.html", {"form": form})


@login_required
def shop(request):
    rewards = Reward.objects.filter(is_active=True).select_related("sponsor").order_by("price")
    sponsors_on = request.institution.has_feature("sponsors")
    context = {
        "rewards": rewards,
        "redemptions": Redemption.objects.filter(user=request.user).select_related("reward", "reward__sponsor")[:10],
        "has_sponsors": sponsors_on and Sponsor.objects.filter(is_active=True).exists(),
        "sponsors_on": sponsors_on,
    }
    return render(request, "web/opportunities/shop.html", context)


@login_required
@require_POST
def redeem(request, pk):
    reward = get_object_or_404(Reward, pk=pk, is_active=True)
    run_service(request, services.redeem, reward, request.user, success=f"«{reward.name}» sizniki! 🎁")
    return redirect("web:shop")
