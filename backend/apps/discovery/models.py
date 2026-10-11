from django.conf import settings
from django.core.validators import MaxValueValidator
from django.db import models
from django.utils import timezone

from apps.profiles.models import Skill


class Challenge(models.Model):
    class Kind(models.TextChoices):
        DAILY = "daily", "Kunlik"
        WEEKLY = "weekly", "Haftalik"
        MONTHLY = "monthly", "Oylik"

    class Difficulty(models.TextChoices):
        EASY = "easy", "Oson"
        MEDIUM = "medium", "O'rta"
        HARD = "hard", "Qiyin"

    DEFAULT_XP = {Kind.DAILY: 10, Kind.WEEKLY: 50, Kind.MONTHLY: 300}

    title = models.CharField("nomi", max_length=200)
    description = models.TextField("shart")
    kind = models.CharField("turi", max_length=10, choices=Kind.choices, default=Kind.WEEKLY)
    difficulty = models.CharField("qiyinlik", max_length=10, choices=Difficulty.choices, default=Difficulty.MEDIUM)
    category = models.CharField(
        "yo'nalish", max_length=20, choices=Skill.Category.choices, default=Skill.Category.OTHER
    )
    xp_reward = models.PositiveIntegerField("XP", blank=True)
    expected_answer = models.CharField(
        "to'g'ri javob",
        max_length=255,
        blank=True,
        help_text="To'ldirilsa, javob avtomatik tekshiriladi (kunlik testlar uchun)",
    )
    faculty = models.ForeignKey(
        "accounts.Faculty",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        help_text="Bo'sh bo'lsa, barcha fakultetlar uchun",
    )
    starts_at = models.DateTimeField("boshlanish", default=timezone.now)
    ends_at = models.DateTimeField("tugash")
    is_published = models.BooleanField("e'lon qilingan", default=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "challenge"
        verbose_name_plural = "challenge'lar"
        ordering = ["-starts_at"]

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        if self.xp_reward is None:
            self.xp_reward = self.DEFAULT_XP[self.kind]
        super().save(*args, **kwargs)

    @property
    def is_open(self) -> bool:
        now = timezone.now()
        return self.is_published and self.starts_at <= now <= self.ends_at


class Submission(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Tekshirilmoqda"
        ACCEPTED = "accepted", "Qabul qilindi"
        REJECTED = "rejected", "Rad etildi"

    challenge = models.ForeignKey(Challenge, on_delete=models.CASCADE, related_name="submissions")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="submissions")
    answer = models.TextField("javob", blank=True)
    link = models.URLField("havola", blank=True, help_text="GitHub, Google Drive va h.k.")
    status = models.CharField("holat", max_length=10, choices=Status.choices, default=Status.PENDING)
    score = models.PositiveSmallIntegerField("baho (0-100)", null=True, blank=True, validators=[MaxValueValidator(100)])
    feedback = models.TextField("izoh", blank=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    xp_awarded = models.PositiveIntegerField(default=0)
    ai_suggestion = models.JSONField("AI taklifi", null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "yechim"
        verbose_name_plural = "yechimlar"
        ordering = ["-created_at"]
        constraints = [models.UniqueConstraint(fields=["challenge", "user"], name="one_submission_per_challenge")]

    def __str__(self):
        return f"{self.user} → {self.challenge}"


class TalentFlag(models.Model):
    """O'qituvchining «bu talabada uchqun bor» belgisi."""

    student = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="talent_flags")
    flagged_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="+")
    area = models.CharField("yo'nalish", max_length=20, choices=Skill.Category.choices)
    note = models.TextField("izoh")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "iqtidor belgisi"
        verbose_name_plural = "iqtidor belgilari"
        ordering = ["-created_at"]
        constraints = [models.UniqueConstraint(fields=["student", "flagged_by", "area"], name="unique_talent_flag")]

    def __str__(self):
        return f"{self.student}: {self.get_area_display()}"
