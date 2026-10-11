from django.conf import settings

from apps.arena.levels import level_for_xp
from apps.discovery.models import Submission
from apps.notifications.services import unread_count
from apps.profiles.models import Achievement


def navigation(request):
    user = getattr(request, "user", None)
    if not (user and user.is_authenticated):
        return {"registration_open": settings.REGISTRATION_OPEN}
    context = {
        "registration_open": settings.REGISTRATION_OPEN,
        "my_level": level_for_xp(user.xp),
        "unread_notifications": unread_count(user),
    }
    if user.is_reviewer:
        context["review_count"] = (
            Submission.objects.filter(status=Submission.Status.PENDING).exclude(user=user).count()
            + Achievement.objects.filter(status=Achievement.Status.PENDING).exclude(user=user).count()
        )
    return context
