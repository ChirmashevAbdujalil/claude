import hashlib
import json

from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.tenants.managers import TenantManager


class AuditLog(models.Model):
    """Kim, qachon, nimani o'zgartirdi. Yozuvlar faqat qo'shiladi: o'zgartirish va o'chirish taqiqlangan.

    Har bir yozuv OTM bo'yicha oldingisining xeshi bilan zanjirlanadi. Bazada kimdir yozuvni qo'lda
    o'zgartirsa yoki o'chirsa, zanjir uziladi va `verify_audit_log` buni ko'rsatadi.
    """

    tenant_path = "institution"

    class Action(models.TextChoices):
        CREATE = "create", "Yaratdi"
        UPDATE = "update", "O'zgartirdi"
        DELETE = "delete", "O'chirdi"
        PASSWORD = "password", "Parolni o'zgartirdi"
        LOGIN = "login", "Tizimga kirdi"
        LOGOUT = "logout", "Tizimdan chiqdi"
        LOGIN_FAILED = "login_failed", "Kirish urinishi muvaffaqiyatsiz"
        EXPORT = "export", "Ma'lumotni yuklab oldi"

    institution = models.ForeignKey(
        "tenants.Institution",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="+",
        verbose_name="OTM",
    )
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
        verbose_name="foydalanuvchi",
    )
    actor_repr = models.CharField("kim", max_length=150)
    actor_role = models.CharField("rol", max_length=40, blank=True)
    action = models.CharField("amal", max_length=20, choices=Action.choices, db_index=True)
    target_type = models.CharField("obyekt turi", max_length=100, blank=True, db_index=True)
    target_label = models.CharField("obyekt nomi", max_length=100, blank=True)
    target_id = models.CharField("obyekt ID", max_length=64, blank=True)
    target_repr = models.CharField("obyekt", max_length=255, blank=True)
    changes = models.JSONField("o'zgarishlar", default=dict, blank=True)
    ip = models.GenericIPAddressField("IP manzil", null=True, blank=True)
    user_agent = models.CharField("brauzer", max_length=255, blank=True)
    created_at = models.DateTimeField("vaqt", default=timezone.now, db_index=True)
    prev_hash = models.CharField(max_length=64, blank=True, editable=False)
    hash = models.CharField(max_length=64, editable=False)

    objects = TenantManager()

    class Meta:
        verbose_name = "jurnal yozuvi"
        verbose_name_plural = "harakatlar jurnali"
        ordering = ["-created_at", "-id"]
        indexes = [models.Index(fields=["institution", "-id"])]

    def __str__(self):
        return f"{self.created_at:%d.%m.%Y %H:%M} · {self.actor_repr} · {self.get_action_display()}"

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValueError("Jurnal yozuvini o'zgartirib bo'lmaydi")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValueError("Jurnal yozuvini o'chirib bo'lmaydi")

    def compute_hash(self) -> str:
        # actor_id kiritilmaydi: foydalanuvchi o'chirilsa SET_NULL bo'ladi, lekin yozuv o'zgarmagan hisoblanadi
        payload = [
            self.prev_hash,
            self.institution_id,
            self.actor_repr,
            self.actor_role,
            self.action,
            self.target_type,
            self.target_id,
            self.target_repr,
            self.changes,
            self.ip,
            self.created_at.isoformat(),
        ]
        raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
        return hashlib.sha256(raw.encode()).hexdigest()
