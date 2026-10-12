from django.conf import settings
from django.db import models

from apps.tenants.managers import TenantManager


class Conversation(models.Model):
    tenant_path = "user__institution"

    class Mode(models.TextChoices):
        MENTOR = "mentor", "AI Mentor"
        IDEA_CHECK = "idea_check", "G'oya tekshiruvchi"
        CAREER = "career", "Kelajakdagi men (karyera)"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="ai_conversations")
    mode = models.CharField("rejim", max_length=20, choices=Mode.choices, default=Mode.MENTOR)
    title = models.CharField("sarlavha", max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = TenantManager()

    class Meta:
        verbose_name = "AI suhbat"
        verbose_name_plural = "AI suhbatlar"
        ordering = ["-updated_at"]

    def __str__(self):
        return self.title or f"{self.get_mode_display()} #{self.pk}"


class Message(models.Model):
    tenant_path = "conversation__user__institution"

    class Role(models.TextChoices):
        USER = "user", "Talaba"
        ASSISTANT = "assistant", "AI"

    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name="messages")
    role = models.CharField(max_length=10, choices=Role.choices)
    content = models.TextField()
    input_tokens = models.PositiveIntegerField(default=0)
    output_tokens = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    objects = TenantManager()

    class Meta:
        verbose_name = "AI xabar"
        verbose_name_plural = "AI xabarlar"
        ordering = ["created_at", "id"]

    def __str__(self):
        return f"{self.get_role_display()}: {self.content[:40]}"
