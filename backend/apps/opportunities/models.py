from django.conf import settings
from django.db import models

from apps.tenants.context import default_institution_id
from apps.tenants.managers import GlobalUniqueChecksMixin, TenantManager


class Opportunity(models.Model):
    tenant_shared = True

    institution = models.ForeignKey(
        "tenants.Institution",
        on_delete=models.CASCADE,
        related_name="opportunities",
        default=default_institution_id,
        null=True,
        blank=True,
        help_text="Bo'sh bo'lsa, platformadagi barcha OTMlarga ko'rinadi",
        verbose_name="OTM",
    )

    class Kind(models.TextChoices):
        GRANT = "grant", "Grant"
        OLYMPIAD = "olympiad", "Olimpiada"
        HACKATHON = "hackathon", "Hakaton"
        INTERNSHIP = "internship", "Stajirovka"
        VACANCY = "vacancy", "Vakansiya"
        FREELANCE = "freelance", "Freelance vazifa"
        INDUSTRY_CASE = "industry_case", "Sanoat muammosi"
        EXCHANGE = "exchange", "Almashinuv dasturi"

    kind = models.CharField("turi", max_length=20, choices=Kind.choices)
    title = models.CharField("nomi", max_length=200)
    description = models.TextField("tavsif")
    organization = models.CharField("tashkilot", max_length=200)
    external_url = models.URLField("havola", blank=True)
    reward = models.CharField("mukofot / maosh", max_length=200, blank=True)
    min_level = models.PositiveSmallIntegerField("minimal daraja", default=1)
    deadline = models.DateTimeField("muddat", null=True, blank=True)
    is_active = models.BooleanField("faol", default=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)

    objects = TenantManager()

    class Meta:
        verbose_name = "imkoniyat"
        verbose_name_plural = "imkoniyatlar"
        ordering = ["deadline", "-created_at"]

    def __str__(self):
        return self.title


class Application(models.Model):
    tenant_path = "user__institution"

    class Status(models.TextChoices):
        SUBMITTED = "submitted", "Yuborilgan"
        SHORTLISTED = "shortlisted", "Saralangan"
        ACCEPTED = "accepted", "Qabul qilingan"
        REJECTED = "rejected", "Rad etilgan"

    opportunity = models.ForeignKey(Opportunity, on_delete=models.CASCADE, related_name="applications")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="applications")
    motivation = models.TextField("motivatsiya xati")
    status = models.CharField("holat", max_length=20, choices=Status.choices, default=Status.SUBMITTED)
    created_at = models.DateTimeField(auto_now_add=True)

    objects = TenantManager()

    class Meta:
        verbose_name = "ariza"
        verbose_name_plural = "arizalar"
        ordering = ["-created_at"]
        constraints = [models.UniqueConstraint(fields=["opportunity", "user"], name="one_application")]

    def __str__(self):
        return f"{self.user} → {self.opportunity}"


class Sponsor(GlobalUniqueChecksMixin, models.Model):
    """Do'kondagi sovg'alarni moliyalashtiradigan kompaniya yoki tashkilot."""

    tenant_shared = True

    institution = models.ForeignKey(
        "tenants.Institution",
        on_delete=models.CASCADE,
        related_name="sponsors",
        default=default_institution_id,
        null=True,
        blank=True,
        help_text="Bo'sh bo'lsa, platformadagi barcha OTMlarga ko'rinadi",
        verbose_name="OTM",
    )
    name = models.CharField("nomi", max_length=200)
    slug = models.SlugField("manzil", unique=True, help_text="Sahifa manzili, masalan: texnosoft")
    logo = models.ImageField("logotip", upload_to="sponsors/", blank=True)
    description = models.TextField("qisqacha tavsif", blank=True)
    website = models.URLField("veb-sayt", blank=True)
    is_active = models.BooleanField("faol", default=True)
    order = models.PositiveSmallIntegerField("tartib", default=0, help_text="Kichik raqam oldinroq chiqadi")
    created_at = models.DateTimeField(auto_now_add=True)

    objects = TenantManager()

    class Meta:
        verbose_name = "homiy"
        verbose_name_plural = "homiylar"
        ordering = ["order", "name"]

    def __str__(self):
        return self.name

    @property
    def initials(self) -> str:
        words = [w for w in self.name.replace("(", " ").split() if w[:1].isalpha()]
        return "".join(w[0] for w in words[:2]).upper() or "?"


class Reward(models.Model):
    """Mukofotlar do'konidagi mahsulot: tangalarga almashtiriladi."""

    institution = models.ForeignKey(
        "tenants.Institution",
        on_delete=models.CASCADE,
        related_name="rewards",
        default=default_institution_id,
        verbose_name="OTM",
    )
    name = models.CharField("nomi", max_length=200)
    description = models.TextField("tavsif", blank=True)
    emoji = models.CharField("belgi", max_length=8, default="🎁", help_text="Rasm bo'lmasa kartochkada ko'rinadi")
    image = models.ImageField("rasm", upload_to="rewards/", blank=True)
    price = models.PositiveIntegerField("narxi (tanga)")
    stock = models.PositiveIntegerField("zaxira", default=0)
    is_active = models.BooleanField("sotuvda", default=True)
    sponsor = models.ForeignKey(
        Sponsor,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="rewards",
        verbose_name="homiy",
        help_text="Sovg'a homiy hisobidan bo'lsa, do'konda uning nomi va logotipi chiqadi",
    )

    objects = TenantManager()

    class Meta:
        verbose_name = "mukofot"
        verbose_name_plural = "mukofotlar do'koni"
        ordering = ["price"]

    def __str__(self):
        return f"{self.name} ({self.price} tanga)"


class Redemption(models.Model):
    tenant_path = "user__institution"

    class Status(models.TextChoices):
        PENDING = "pending", "Tayyorlanmoqda"
        DELIVERED = "delivered", "Topshirildi"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="redemptions")
    reward = models.ForeignKey(Reward, on_delete=models.PROTECT, related_name="redemptions")
    price = models.PositiveIntegerField("to'langan tanga")
    status = models.CharField("holat", max_length=20, choices=Status.choices, default=Status.PENDING)
    created_at = models.DateTimeField(auto_now_add=True)

    objects = TenantManager()

    class Meta:
        verbose_name = "xarid"
        verbose_name_plural = "xaridlar"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user}: {self.reward.name}"
