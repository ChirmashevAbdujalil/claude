from django.conf import settings
from django.db import models


class Opportunity(models.Model):
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

    class Meta:
        verbose_name = "imkoniyat"
        verbose_name_plural = "imkoniyatlar"
        ordering = ["deadline", "-created_at"]

    def __str__(self):
        return self.title


class Application(models.Model):
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

    class Meta:
        verbose_name = "ariza"
        verbose_name_plural = "arizalar"
        ordering = ["-created_at"]
        constraints = [models.UniqueConstraint(fields=["opportunity", "user"], name="one_application")]

    def __str__(self):
        return f"{self.user} → {self.opportunity}"


class Reward(models.Model):
    """Mukofotlar do'konidagi mahsulot: tangalarga almashtiriladi."""

    name = models.CharField("nomi", max_length=200)
    description = models.TextField("tavsif", blank=True)
    image = models.ImageField("rasm", upload_to="rewards/", blank=True)
    price = models.PositiveIntegerField("narxi (tanga)")
    stock = models.PositiveIntegerField("zaxira", default=0)
    is_active = models.BooleanField("sotuvda", default=True)

    class Meta:
        verbose_name = "mukofot"
        verbose_name_plural = "mukofotlar do'koni"
        ordering = ["price"]

    def __str__(self):
        return f"{self.name} ({self.price} tanga)"


class Redemption(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Tayyorlanmoqda"
        DELIVERED = "delivered", "Topshirildi"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="redemptions")
    reward = models.ForeignKey(Reward, on_delete=models.PROTECT, related_name="redemptions")
    price = models.PositiveIntegerField("to'langan tanga")
    status = models.CharField("holat", max_length=20, choices=Status.choices, default=Status.PENDING)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "xarid"
        verbose_name_plural = "xaridlar"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user}: {self.reward.name}"
