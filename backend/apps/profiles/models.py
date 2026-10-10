from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


class Skill(models.Model):
    class Category(models.TextChoices):
        PROGRAMMING = "programming", "Dasturlash"
        ENGINEERING = "engineering", "Muhandislik"
        DESIGN = "design", "Dizayn"
        RESEARCH = "research", "Tadqiqot"
        LEADERSHIP = "leadership", "Liderlik"
        LANGUAGES = "languages", "Tillar"
        OTHER = "other", "Boshqa"

    name = models.CharField("nomi", max_length=100, unique=True)
    category = models.CharField("yo'nalish", max_length=20, choices=Category.choices, default=Category.OTHER)

    class Meta:
        verbose_name = "ko'nikma"
        verbose_name_plural = "ko'nikmalar"
        ordering = ["category", "name"]

    def __str__(self):
        return self.name


class UserSkill(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="skills")
    skill = models.ForeignKey(Skill, on_delete=models.CASCADE, related_name="user_skills", verbose_name="ko'nikma")
    level = models.PositiveSmallIntegerField(
        "daraja", default=1, validators=[MinValueValidator(1), MaxValueValidator(5)]
    )

    class Meta:
        verbose_name = "talaba ko'nikmasi"
        verbose_name_plural = "talaba ko'nikmalari"
        constraints = [models.UniqueConstraint(fields=["user", "skill"], name="unique_user_skill")]

    def __str__(self):
        return f"{self.user}: {self.skill} ({self.level})"


class Endorsement(models.Model):
    """O'qituvchi talabaning ko'nikmasini tasdiqlaydi."""

    user_skill = models.ForeignKey(UserSkill, on_delete=models.CASCADE, related_name="endorsements")
    endorsed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="given_endorsements"
    )
    comment = models.CharField("izoh", max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "tasdiq"
        verbose_name_plural = "tasdiqlar"
        constraints = [models.UniqueConstraint(fields=["user_skill", "endorsed_by"], name="unique_endorsement")]

    def __str__(self):
        return f"{self.endorsed_by} → {self.user_skill}"


class Achievement(models.Model):
    class Kind(models.TextChoices):
        OLYMPIAD = "olympiad", "Olimpiada"
        HACKATHON = "hackathon", "Hakaton"
        CERTIFICATE = "certificate", "Sertifikat"
        PUBLICATION = "publication", "Ilmiy maqola"
        PATENT = "patent", "Patent / ixtiro"
        SPORT = "sport", "Sport"
        ART = "art", "Ijod"
        OTHER = "other", "Boshqa"

    class Status(models.TextChoices):
        PENDING = "pending", "Kutilmoqda"
        APPROVED = "approved", "Tasdiqlangan"
        REJECTED = "rejected", "Rad etilgan"

    DEFAULT_XP = {
        Kind.OLYMPIAD: 300,
        Kind.HACKATHON: 300,
        Kind.CERTIFICATE: 100,
        Kind.PUBLICATION: 400,
        Kind.PATENT: 600,
        Kind.SPORT: 150,
        Kind.ART: 150,
        Kind.OTHER: 50,
    }
    MAX_XP = 1000

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="achievements")
    kind = models.CharField("turi", max_length=20, choices=Kind.choices)
    title = models.CharField("nomi", max_length=200)
    description = models.TextField("tavsif", blank=True)
    proof = models.FileField("tasdiqlovchi hujjat", upload_to="achievements/", blank=True)
    proof_url = models.URLField("havola", blank=True)
    achieved_on = models.DateField("sana")
    status = models.CharField("holat", max_length=20, choices=Status.choices, default=Status.PENDING)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    review_comment = models.CharField("tekshiruvchi izohi", max_length=255, blank=True)
    xp_awarded = models.PositiveIntegerField("berilgan XP", default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "yutuq"
        verbose_name_plural = "yutuqlar"
        ordering = ["-achieved_on", "-id"]

    def __str__(self):
        return f"{self.user}: {self.title}"
