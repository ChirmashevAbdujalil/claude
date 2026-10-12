from django.contrib.auth.models import UserManager
from django.db import models

from .context import current, unscoped


def _scope(queryset, path: str, shared: bool):
    institution = current()
    if institution is None:
        return queryset
    condition = models.Q(**{path: institution})
    if shared:
        condition |= models.Q(**{f"{path}__isnull": True})
    return queryset.filter(condition)


class TenantManager(models.Manager):
    """Joriy OTM bo'yicha avtomatik cheklaydigan menejer.

    Model atributlari:
    - tenant_path: OTMgacha bo'lgan yo'l, masalan "institution" yoki "user__institution";
    - tenant_shared: True bo'lsa, OTMsiz (hamma uchun umumiy) yozuvlar ham ko'rinadi.

    Sozlama modelda saqlanadi, chunki Django bog'langan menejerlarni (masalan, user.posts) argumentsiz yaratadi.
    """

    def get_queryset(self):
        path = getattr(self.model, "tenant_path", "institution")
        shared = getattr(self.model, "tenant_shared", False)
        return _scope(super().get_queryset(), path, shared)


class TenantUserManager(UserManager):
    def get_queryset(self):
        return _scope(super().get_queryset(), "institution", False)


class GlobalUniqueChecksMixin:
    """Butun platforma bo'yicha noyob maydonlar (login, portfolio manzili) uchun forma tekshiruvi.

    Django noyoblikni standart menejer orqali tekshiradi; u joriy OTM bilan cheklangan, shuning uchun
    boshqa OTMdagi takrorni ko'rmaydi. Bu yerda tekshiruv barcha OTMlar bo'yicha bajariladi.
    """

    def _perform_unique_checks(self, unique_checks):
        with unscoped():
            return super()._perform_unique_checks(unique_checks)
