from django.contrib.auth.models import AbstractUser
from django.db import models

from apps.tenants.context import default_institution_id
from apps.tenants.managers import GlobalUniqueChecksMixin, TenantManager, TenantUserManager


class Faculty(models.Model):
    institution = models.ForeignKey(
        "tenants.Institution",
        on_delete=models.CASCADE,
        related_name="faculties",
        default=default_institution_id,
        verbose_name="OTM",
    )
    name = models.CharField("nomi", max_length=200)
    short_name = models.CharField("qisqa nomi", max_length=20)

    objects = TenantManager()

    class Meta:
        verbose_name = "fakultet"
        verbose_name_plural = "fakultetlar"
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(fields=["institution", "name"], name="faculty_unique_name_per_institution"),
            models.UniqueConstraint(fields=["institution", "short_name"], name="faculty_unique_short_per_institution"),
        ]

    def __str__(self):
        return self.name


class User(GlobalUniqueChecksMixin, AbstractUser):
    class Role(models.TextChoices):
        STUDENT = "student", "Talaba"
        TEACHER = "teacher", "O'qituvchi"
        MENTOR = "mentor", "Mentor"
        PARTNER = "partner", "Hamkor"
        DEAN = "dean", "Dekanat"
        RECTOR = "rector", "Rektorat"
        ADMIN = "admin", "Admin"

    # Talabalarni baholash va tasdiqlash huquqiga ega rollar
    REVIEWER_ROLES = {Role.TEACHER, Role.DEAN, Role.RECTOR, Role.ADMIN}
    # Statistika va boshqaruv paneliga kira oladigan rollar
    MANAGEMENT_ROLES = {Role.DEAN, Role.RECTOR, Role.ADMIN}

    role = models.CharField("rol", max_length=20, choices=Role.choices, default=Role.STUDENT)
    telegram_id = models.BigIntegerField("Telegram ID", unique=True, null=True, blank=True)
    faculty = models.ForeignKey(
        Faculty,
        verbose_name="fakultet",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="users",
    )
    course = models.PositiveSmallIntegerField("kurs", null=True, blank=True)
    bio = models.TextField("o'zi haqida", blank=True)
    avatar = models.ImageField("avatar", upload_to="avatars/", blank=True)
    github_url = models.URLField("GitHub", blank=True)
    linkedin_url = models.URLField("LinkedIn", blank=True)
    portfolio_slug = models.SlugField("portfolio manzili", unique=True, null=True, blank=True)
    is_public = models.BooleanField("profil ommaviy", default=True)
    onboarded_at = models.DateTimeField("boshlang'ich sozlash tugagan", null=True, blank=True)

    # Ball iqtisodiyoti: tezkor reyting uchun denormalizatsiya qilingan qiymatlar.
    # Haqiqiy manba arena.XpTransaction jurnali.
    xp = models.PositiveIntegerField("XP", default=0, db_index=True)
    coins = models.PositiveIntegerField("tangalar", default=0)

    institution = models.ForeignKey(
        "tenants.Institution",
        on_delete=models.PROTECT,
        related_name="users",
        default=default_institution_id,
        verbose_name="OTM",
    )

    objects = TenantUserManager()

    class Meta:
        verbose_name = "foydalanuvchi"
        verbose_name_plural = "foydalanuvchilar"

    def __str__(self):
        return self.get_full_name() or self.username

    @property
    def is_reviewer(self) -> bool:
        return self.is_superuser or self.role in self.REVIEWER_ROLES

    @property
    def is_institution_admin(self) -> bool:
        """OTM sozlamalarini boshqara oladi (rektorat yoki administrator)."""
        return self.is_superuser or self.role in {self.Role.RECTOR, self.Role.ADMIN}

    @property
    def is_management(self) -> bool:
        return self.is_superuser or self.role in self.MANAGEMENT_ROLES
