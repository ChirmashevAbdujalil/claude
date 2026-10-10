from apps.arena.levels import level_for_xp
from apps.discovery.models import Submission
from apps.profiles.models import Achievement


def navigation(request):
    user = getattr(request, "user", None)
    if not (user and user.is_authenticated):
        return {}
    context = {"my_level": level_for_xp(user.xp)}
    if user.is_reviewer:
        context["review_count"] = (
            Submission.objects.filter(status=Submission.Status.PENDING).exclude(user=user).count()
            + Achievement.objects.filter(status=Achievement.Status.PENDING).exclude(user=user).count()
        )
    return context
