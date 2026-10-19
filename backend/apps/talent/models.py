from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.tenants.managers import TenantManager

from .tracks import Track


class TalentProfile(models.Model):
    """Iqtidorlar reyestridagi yozuv: bitta talaba, uning yo'nalishi, mentori va holati."""

    tenant_path = "student__institution"

    class Status(models.TextChoices):
        IDENTIFIED = "identified", "Aniqlangan"
        MENTORED = "mentored", "Mentor biriktirilgan"
        DEVELOPING = "developing", "Rivojlanmoqda"
        ACHIEVED = "achieved", "Natijaga erishgan"
        ARCHIVED = "archived", "Arxivda"

    class Source(models.TextChoices):
        FLAG = "flag", "O'qituvchi belgisi"
        ACHIEVEMENT = "achievement", "Tasdiqlangan yutuq"
        RATING = "rating", "Reyting"
        DIAGNOSTIC = "diagnostic", "Diagnostika"
        MANUAL = "manual", "Rahbariyat qo'shgan"
        SURVEY = "survey", "So'rovnoma"

    PIPELINE = [Status.IDENTIFIED, Status.MENTORED, Status.DEVELOPING, Status.ACHIEVED]

    student = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="talent_profile", verbose_name="talaba"
    )
    track = models.CharField("yo'nalish", max_length=20, choices=Track.choices, blank=True)
    source = models.CharField("qayerdan aniqlandi", max_length=20, choices=Source.choices, default=Source.MANUAL)
    status = models.CharField("holat", max_length=20, choices=Status.choices, default=Status.IDENTIFIED, db_index=True)
    mentor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="mentees",
        verbose_name="mentor",
    )
    mentor_assigned_at = models.DateTimeField("mentor biriktirilgan vaqt", null=True, blank=True)
    note = models.TextField("izoh", blank=True)
    added_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    created_at = models.DateTimeField("reyestrga kiritilgan", default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    objects = TenantManager()

    class Meta:
        verbose_name = "iqtidorli talaba"
        verbose_name_plural = "iqtidorlar reyestri"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.student} · {self.get_track_display() or 'yo`nalish belgilanmagan'}"

    @property
    def stage(self) -> int:
        """Holat zanjiridagi o'rni: 1..4 (arxiv uchun 0)."""
        return self.PIPELINE.index(self.status) + 1 if self.status in self.PIPELINE else 0


class DevelopmentGoal(models.Model):
    """Shaxsiy rivojlanish rejasidagi maqsad: muddati, holati va mentor izohi bilan."""

    tenant_path = "profile__student__institution"

    class Kind(models.TextChoices):
        OLYMPIAD = "olympiad", "Olimpiadaga tayyorlanish"
        PUBLICATION = "publication", "Maqola yoki tezis"
        PROJECT = "project", "Loyiha"
        STARTUP = "startup", "Startap"
        COMPETITION = "competition", "Tanlov yoki hakaton"
        CERTIFICATE = "certificate", "Sertifikat (til, IT)"
        PATENT = "patent", "Ixtiro yoki patent"
        OTHER = "other", "Boshqa"

    class Status(models.TextChoices):
        PLANNED = "planned", "Rejalashtirilgan"
        IN_PROGRESS = "in_progress", "Bajarilmoqda"
        DONE = "done", "Bajarildi"
        CANCELLED = "cancelled", "Bekor qilindi"

    OPEN = {Status.PLANNED, Status.IN_PROGRESS}

    profile = models.ForeignKey(TalentProfile, on_delete=models.CASCADE, related_name="goals")
    title = models.CharField("maqsad", max_length=200)
    kind = models.CharField("turi", max_length=20, choices=Kind.choices, default=Kind.OTHER)
    due_date = models.DateField("muddat")
    status = models.CharField("holat", max_length=20, choices=Status.choices, default=Status.PLANNED)
    progress = models.PositiveSmallIntegerField("bajarilish, %", default=0)
    student_note = models.CharField("talaba izohi", max_length=300, blank=True)
    mentor_comment = models.CharField("mentor izohi", max_length=300, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    completed_at = models.DateTimeField("bajarilgan vaqt", null=True, blank=True)
    reminded_on = models.DateField(null=True, blank=True, editable=False)
    overdue_notified = models.BooleanField(default=False, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = TenantManager()

    class Meta:
        verbose_name = "rivojlanish maqsadi"
        verbose_name_plural = "rivojlanish rejalari"
        ordering = ["due_date", "id"]

    def __str__(self):
        return self.title

    @property
    def is_open(self) -> bool:
        return self.status in self.OPEN

    @property
    def is_overdue(self) -> bool:
        return self.is_open and self.due_date < timezone.localdate()


class DiagnosticResult(models.Model):
    """Iqtidor diagnostikasi natijasi: javoblar, yo'nalishlar bo'yicha ball va tavsiya etilgan yo'nalish."""

    tenant_path = "user__institution"

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="talent_diagnostic", verbose_name="talaba"
    )
    answers = models.JSONField("javoblar", default=dict)
    scores = models.JSONField("ballar", default=dict)
    track = models.CharField("tavsiya etilgan yo'nalish", max_length=20, choices=Track.choices)
    second_track = models.CharField("ikkinchi yo'nalish", max_length=20, choices=Track.choices, blank=True)
    taken_at = models.DateTimeField(auto_now=True)

    objects = TenantManager()

    class Meta:
        verbose_name = "diagnostika natijasi"
        verbose_name_plural = "diagnostika natijalari"

    def __str__(self):
        return f"{self.user}: {self.get_track_display()}"

    def ranked(self):
        """[(yo'nalish, ball)] kamayish tartibida."""
        return sorted(((t, self.scores.get(t, 0)) for t in Track.values), key=lambda pair: -pair[1])
