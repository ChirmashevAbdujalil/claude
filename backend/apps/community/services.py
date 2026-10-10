from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from apps.arena import services as arena

from .models import Event, EventRegistration

# Tadbir boshlanishidan 30 daqiqa oldin va tugaganidan 1 soat keyingacha check-in ochiq
CHECKIN_OPENS_BEFORE = timedelta(minutes=30)
CHECKIN_CLOSES_AFTER = timedelta(hours=1)


class EventError(Exception):
    pass


@transaction.atomic
def register(event: Event, user) -> EventRegistration:
    event = Event.objects.select_for_update().get(pk=event.pk)
    if event.ends_at < timezone.now():
        raise EventError("Tadbir yakunlangan")
    if EventRegistration.objects.filter(event=event, user=user).exists():
        raise EventError("Siz allaqachon ro'yxatdan o'tgansiz")
    if event.capacity is not None and event.registrations.count() >= event.capacity:
        raise EventError("O'rinlar qolmadi")
    return EventRegistration.objects.create(event=event, user=user)


@transaction.atomic
def check_in(code: str, user) -> EventRegistration:
    """Tadbirdagi QR kodni skanerlash: qatnashish qayd qilinadi va XP beriladi."""
    event = Event.objects.filter(checkin_code=code).first()
    if event is None:
        raise EventError("QR kod noto'g'ri")
    now = timezone.now()
    if not (event.starts_at - CHECKIN_OPENS_BEFORE <= now <= event.ends_at + CHECKIN_CLOSES_AFTER):
        raise EventError("Check-in faqat tadbir vaqtida ishlaydi")
    registration, _ = EventRegistration.objects.select_for_update().get_or_create(event=event, user=user)
    if registration.attended_at:
        raise EventError("Siz allaqachon check-in qilgansiz")
    registration.attended_at = now
    registration.save(update_fields=["attended_at"])
    arena.award(user, arena.Reason.EVENT, event.xp_reward, ref=f"event:{event.pk}", note=event.title)
    arena.touch_streak(user)
    return registration
