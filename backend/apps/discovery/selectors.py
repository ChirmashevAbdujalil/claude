from django.db.models import Q
from django.utils import timezone

from .models import Challenge


def visible_challenges(user, include_closed: bool = False):
    """Foydalanuvchi ko'ra oladigan challenge'lar: o'qituvchilar hammasini ko'radi."""
    qs = Challenge.objects.all()
    if user.is_reviewer:
        return qs
    now = timezone.now()
    qs = qs.filter(is_published=True, starts_at__lte=now).filter(
        Q(faculty__isnull=True) | Q(faculty_id=user.faculty_id)
    )
    if not include_closed:
        qs = qs.filter(ends_at__gte=now)
    return qs
