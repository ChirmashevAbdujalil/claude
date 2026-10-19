from apps.arena.levels import level_for_xp
from apps.discovery.models import Submission
from apps.notifications.services import unread_count
from apps.profiles.models import Achievement
from apps.surveys import services as survey_services
from apps.surveys.models import IssuedAccount
from apps.tenants import services as tenant_services

DEFAULT_COLORS = ("#062d3b", "#168a9c")


def branding(institution) -> dict:
    """OTM nomi, shiori va ranglari: barcha sahifalar uchun."""
    if institution is None:
        return {
            "institution": None,
            "brand_name": "Talent Hub",
            "institution_name": "OTMlar uchun iqtidorlar platformasi",
            "institution_short": "Talent Hub",
            "institution_tagline": "",
            "theme_colors": None,
            "features": set(),
        }
    colors = (institution.color_dark, institution.color_light)
    custom = institution.has_feature("branding") and colors != DEFAULT_COLORS
    return {
        "institution": institution,
        "brand_name": institution.brand_name,
        "institution_name": institution.name,
        "institution_short": institution.short_name,
        "institution_tagline": institution.tagline,
        "theme_colors": colors if custom else None,
        "features": institution.plan_info["features"],
    }


def navigation(request):
    institution = getattr(request, "institution", None)
    context = branding(institution)
    context["registration_open"] = tenant_services.registration_state(institution)[0]
    user = getattr(request, "user", None)
    if not (user and user.is_authenticated):
        return context
    context |= {
        "my_level": level_for_xp(user.xp),
        "unread_notifications": unread_count(user),
    }
    if user.role == user.Role.STUDENT:
        context["open_surveys_count"] = survey_services.open_for(user).count()
        context["must_change_password"] = IssuedAccount.objects.filter(user=user, must_change_password=True).exists()
    if user.is_reviewer:
        context["review_count"] = (
            Submission.objects.filter(status=Submission.Status.PENDING).exclude(user=user).count()
            + Achievement.objects.filter(status=Achievement.Status.PENDING).exclude(user=user).count()
        )
    return context
