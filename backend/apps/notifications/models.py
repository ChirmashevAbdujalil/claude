from django.conf import settings
from django.db import models

from apps.tenants.managers import TenantManager


class Notification(models.Model):
    tenant_path = "user__institution"

    class Kind(models.TextChoices):
        SUCCESS = "success", "Yutuq"
        INFO = "info", "Ma'lumot"
        WARNING = "warning", "Diqqat"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notifications")
    kind = models.CharField("turi", max_length=10, choices=Kind.choices, default=Kind.INFO)
    icon = models.CharField("belgi", max_length=10, default="🔔")
    title = models.CharField("sarlavha", max_length=200)
    body = models.CharField("matn", max_length=500, blank=True)
    url = models.CharField("havola", max_length=300, blank=True, help_text="Sayt ichidagi yo'l, masalan /challenges/3/")
    is_read = models.BooleanField("o'qilgan", default=False, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    objects = TenantManager()

    class Meta:
        verbose_name = "bildirishnoma"
        verbose_name_plural = "bildirishnomalar"
        ordering = ["-created_at", "-id"]

    def __str__(self):
        return f"{self.user}: {self.title}"
