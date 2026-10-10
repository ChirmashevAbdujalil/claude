from functools import wraps

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator

from apps.ai.services import AiError
from apps.arena.services import InsufficientCoins
from apps.community.services import EventError
from apps.discovery.services import SubmissionError
from apps.opportunities.services import OpportunityError
from apps.profiles.services import ReviewError
from apps.projects.services import ProjectError

# Servis qatlamidagi talabaga ko'rsatiladigan xatolar
SERVICE_ERRORS = (
    AiError,
    EventError,
    InsufficientCoins,
    OpportunityError,
    ProjectError,
    ReviewError,
    SubmissionError,
)


def run_service(request, func, *args, success=None, **kwargs):
    """Servisni chaqiradi; xato bo'lsa xabar ko'rsatib `None` qaytaradi."""
    try:
        result = func(*args, **kwargs)
    except SERVICE_ERRORS as exc:
        messages.error(request, str(exc))
        return None
    if success:
        messages.success(request, success)
    return result


def paginate(request, queryset, per_page=12):
    return Paginator(queryset, per_page).get_page(request.GET.get("page"))


def reviewer_required(view):
    @login_required
    @wraps(view)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_reviewer:
            raise PermissionDenied
        return view(request, *args, **kwargs)

    return wrapper


def management_required(view):
    @login_required
    @wraps(view)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_management:
            raise PermissionDenied
        return view(request, *args, **kwargs)

    return wrapper
