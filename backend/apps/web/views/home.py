from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.utils import timezone

from apps.arena import selectors as arena_selectors
from apps.arena.models import Streak
from apps.community.models import Event
from apps.discovery.models import Challenge, Submission
from apps.discovery.selectors import visible_challenges
from apps.opportunities.models import Opportunity
from apps.profiles.models import Achievement
from apps.projects.models import ProjectMember


@login_required
def dashboard(request):
    user = request.user
    submitted = Submission.objects.filter(user=user).values_list("challenge_id", flat=True)
    open_challenges = visible_challenges(user).exclude(pk__in=submitted).order_by("ends_at")
    if user.is_reviewer:
        open_challenges = open_challenges.filter(
            is_published=True, starts_at__lte=timezone.now(), ends_at__gte=timezone.now()
        )
    daily = open_challenges.filter(kind=Challenge.Kind.DAILY).first()

    context = {
        "streak": Streak.objects.filter(user=user).first(),
        "rank": arena_selectors.leaderboard(user).me,
        "daily": daily,
        "challenges": open_challenges.exclude(pk=getattr(daily, "pk", None))[:3],
        "events": Event.objects.filter(ends_at__gte=timezone.now()).order_by("starts_at")[:3],
        "badges": user.badges.select_related("badge")[:6],
        "memberships": ProjectMember.objects.filter(user=user, status="active").select_related("project")[:3],
        "opportunities": Opportunity.objects.filter(is_active=True).order_by("-created_at")[:3],
        "pending_reviews": (
            Submission.objects.filter(status=Submission.Status.PENDING).count()
            + Achievement.objects.filter(status=Achievement.Status.PENDING).count()
            if user.is_reviewer
            else 0
        ),
    }
    return render(request, "web/dashboard.html", context)
