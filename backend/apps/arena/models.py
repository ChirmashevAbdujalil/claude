from django.conf import settings
from django.db import models
from django.db.models import Q

from apps.tenants.managers import TenantManager


class PointTransaction(models.Model):
    """XP va tangalar jurnali. Foydalanuvchidagi xp/coins qiymatlari shundan kelib chiqadi."""

    tenant_path = "user__institution"

    class Reason(models.TextChoices):
        CHALLENGE = "challenge", "Challenge yechimi"
        ACHIEVEMENT = "achievement", "Tasdiqlangan yutuq"
        ENDORSEMENT = "endorsement", "Ko'nikma tasdig'i"
        EVENT = "event", "Tadbirda qatnashish"
        PROJECT = "project", "Loyiha bosqichi"
        STREAK = "streak", "Streak bonusi"
        BADGE = "badge", "Nishon bonusi"
        REDEMPTION = "redemption", "Mukofot xaridi"
        MANUAL = "manual", "Qo'lda berilgan"
        SURVEY = "survey", "So'rovnomada qatnashish"

    # Kunlik limitga kirmaydigan sabablar: ular o'qituvchi tasdig'idan o'tadi yoki ball sarflaydi
    UNCAPPED_REASONS = {Reason.ACHIEVEMENT, Reason.REDEMPTION, Reason.MANUAL}

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="transactions",
        verbose_name="foydalanuvchi",
    )
    xp = models.PositiveIntegerField("XP", default=0)
    coins = models.IntegerField("tangalar", default=0)
    reason = models.CharField("sabab", max_length=20, choices=Reason.choices)
    ref = models.CharField(
        "manba",
        max_length=100,
        blank=True,
        help_text="Bir manba uchun ball ikki marta berilmasligini ta'minlaydi, masalan 'submission:12'",
    )
    note = models.CharField("izoh", max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    objects = TenantManager()

    class Meta:
        verbose_name = "ball tranzaksiyasi"
        verbose_name_plural = "ball tranzaksiyalari"
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "reason", "ref"], condition=~Q(ref=""), name="unique_award_per_source"
            )
        ]

    def __str__(self):
        return f"{self.user} +{self.xp} XP ({self.get_reason_display()})"


class Badge(models.Model):
    code = models.SlugField("kod", unique=True)
    name = models.CharField("nomi", max_length=100)
    description = models.CharField("tavsif", max_length=255)
    icon = models.CharField("belgi", max_length=10, default="🏅")
    xp_bonus = models.PositiveIntegerField("XP bonus", default=0)

    class Meta:
        verbose_name = "nishon"
        verbose_name_plural = "nishonlar"
        ordering = ["name"]

    def __str__(self):
        return f"{self.icon} {self.name}"


class UserBadge(models.Model):
    tenant_path = "user__institution"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="badges")
    badge = models.ForeignKey(Badge, on_delete=models.CASCADE, related_name="holders")
    awarded_at = models.DateTimeField(auto_now_add=True)

    objects = TenantManager()

    class Meta:
        verbose_name = "berilgan nishon"
        verbose_name_plural = "berilgan nishonlar"
        constraints = [models.UniqueConstraint(fields=["user", "badge"], name="unique_user_badge")]
        ordering = ["-awarded_at"]

    def __str__(self):
        return f"{self.user}: {self.badge}"


class Streak(models.Model):
    tenant_path = "user__institution"

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="streak")
    current = models.PositiveIntegerField("joriy", default=0)
    longest = models.PositiveIntegerField("eng uzun", default=0)
    last_active = models.DateField("oxirgi faollik", null=True, blank=True)

    objects = TenantManager()

    class Meta:
        verbose_name = "streak"
        verbose_name_plural = "streaklar"

    def __str__(self):
        return f"{self.user}: {self.current} kun"
