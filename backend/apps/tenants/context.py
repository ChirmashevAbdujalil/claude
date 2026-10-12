"""Joriy OTM (tenant) konteksti.

Har bir so'rov boshida middleware joriy OTMni o'rnatadi. Tenant modellarining menejerlari shu qiymat
bo'yicha so'rovlarni avtomatik cheklaydi, shuning uchun bir OTM boshqasining ma'lumotini ko'rmaydi.
Kontekst o'rnatilmagan bo'lsa (migratsiya, boshqaruv buyruqlari, fon vazifalari), filtr qo'llanmaydi.
"""

from contextlib import contextmanager
from contextvars import ContextVar

from django.conf import settings

_current = ContextVar("current_institution", default=None)


def current():
    return _current.get()


@contextmanager
def activate(institution):
    token = _current.set(institution)
    try:
        yield institution
    finally:
        _current.reset(token)


@contextmanager
def unscoped():
    """Barcha OTMlar bo'yicha ishlash uchun (platforma statistikasi, OTMlararo liga)."""
    token = _current.set(None)
    try:
        yield
    finally:
        _current.reset(token)


def default_slug() -> str:
    return settings.DEFAULT_INSTITUTION_SLUG


def default_institution():
    from .models import Institution

    institution = Institution.objects.filter(slug=default_slug()).first()
    if institution is None:
        institution = Institution.objects.create(
            slug=default_slug(), name=settings.DEFAULT_INSTITUTION_NAME, short_name=settings.DEFAULT_INSTITUTION_SHORT
        )
    return institution


def default_institution_id():
    """Yangi yozuv uchun standart OTM: joriy OTM, bo'lmasa asosiy OTM.

    Faqat `id` tanlanadi: bu funksiya migratsiyalarda ham chaqiriladi, o'shanda keyingi ustunlar
    hali yo'q bo'lishi mumkin.
    """
    institution = current()
    if institution is not None:
        return institution.pk
    from django.db import DatabaseError

    from .models import Institution

    try:
        pk = Institution.objects.filter(slug=default_slug()).values_list("pk", flat=True).first()
    except DatabaseError:
        return None  # jadval hali yaratilmagan (makemigrations paytida)
    return pk if pk is not None else default_institution().pk
