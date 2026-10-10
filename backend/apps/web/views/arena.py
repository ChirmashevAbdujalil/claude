from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from apps.accounts.models import Faculty
from apps.arena import selectors
from apps.arena.models import Badge, PointTransaction, Streak

from .common import paginate

TABS = [("leaderboard", "Reyting"), ("league", "Fakultetlar ligasi"), ("badges", "Nishonlar"), ("history", "Tarix")]
PERIODS = [("all", "Umumiy"), ("month", "30 kun"), ("week", "7 kun")]


@login_required
def arena(request):
    tab = request.GET.get("tab", "leaderboard")
    user = request.user
    context = {
        "tab": tab,
        "tabs": TABS,
        "streak": Streak.objects.filter(user=user).first(),
    }
    if tab == "league":
        since, rows = selectors.faculty_league()
        top = max((row["xp"] for row in rows), default=0)
        context.update(since=since, league=rows, league_top=top)
    elif tab == "badges":
        earned = {ub.badge_id: ub for ub in user.badges.all()}
        badges = list(Badge.objects.all())
        for badge in badges:
            badge.earned = earned.get(badge.pk)
        badges.sort(key=lambda b: (b.earned is None, b.name))
        context.update(badges=badges, earned_count=len(earned))
    elif tab == "history":
        context["page"] = paginate(request, PointTransaction.objects.filter(user=user), per_page=20)
    else:
        context["tab"] = "leaderboard"
        period = request.GET.get("period", "all")
        faculty = request.GET.get("faculty")
        board = selectors.leaderboard(user, period, faculty)
        context.update(
            board=board,
            periods=PERIODS,
            faculties=Faculty.objects.all(),
            faculty=faculty or "",
            podium=board.rows[:3],
        )
    return render(request, "web/arena/index.html", context)
