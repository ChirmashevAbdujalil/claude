import re

from django.conf import settings
from django.core.validators import RegexValidator
from django.db import models

from . import plans

hex_color = RegexValidator(r"^#[0-9a-fA-F]{6}$", "Rang #RRGGBB ko'rinishida bo'lishi kerak, masalan #062d3b")


class Institution(models.Model):
    """Platformaga ulangan OTM (tenant)."""

    name = models.CharField("to'liq nomi", max_length=200)
    short_name = models.CharField("qisqa nomi", max_length=20, help_text="Masalan: ANDTI. Sayt nomida chiqadi")
    slug = models.SlugField(
        "manzil", unique=True, help_text="Subdomen: <manzil>.talenthub.uz. Faqat lotin harflari, raqam va chiziqcha"
    )
    domain = models.CharField(
        "o'z domeni",
        max_length=200,
        blank=True,
        help_text="Ixtiyoriy: OTMning o'z domeni, masalan talent.andti.uz (DNS shu serverga yo'naltirilishi kerak)",
    )
    tagline = models.CharField(
        "shior", max_length=120, blank=True, help_text="Masalan: Ta'lim · Fan · Ishlab chiqarish"
    )
    logo = models.ImageField("logotip", upload_to="institutions/", blank=True)
    color_dark = models.CharField("asosiy rang (to'q)", max_length=7, default="#062d3b", validators=[hex_color])
    color_light = models.CharField("asosiy rang (och)", max_length=7, default="#168a9c", validators=[hex_color])
    plan = models.CharField("tarif", max_length=20, choices=plans.CHOICES, default="pilot")
    paid_until = models.DateField("to'langan muddat", null=True, blank=True)
    registration_open = models.BooleanField("talabalar o'zi ro'yxatdan o'tadi", default=True)
    show_in_league = models.BooleanField("OTMlararo ligada qatnashadi", default=True)
    is_active = models.BooleanField("faol", default=True, help_text="O'chirilsa, OTM sayti vaqtincha yopiladi")
    contact_name = models.CharField("mas'ul shaxs", max_length=200, blank=True)
    contact_phone = models.CharField("telefon", max_length=30, blank=True)
    contact_email = models.EmailField("email", blank=True)
    # So'rovnoma sahifalaridagi «mas'ul shaxs» bloki: kim javobgar va qayerda e'lonlar chiqadi
    curator_enabled = models.BooleanField(
        "so'rovnomalarda mas'ul shaxsni ko'rsatish",
        default=False,
        help_text="«Rahmat» sahifasida rasm, ism va havola bilan blok, to'ldirish sahifasi pastida imzo chiqadi",
    )
    curator_name = models.CharField("mas'ul shaxs (F.I.Sh.)", max_length=120, blank=True)
    curator_title = models.CharField("lavozimi", max_length=120, blank=True)
    curator_photo = models.ImageField("rasmi", upload_to="institutions/", blank=True)
    curator_url = models.URLField(
        "e'lonlar havolasi", blank=True, help_text="Masalan, Telegram kanal: https://t.me/kanal_nomi"
    )
    curator_message = models.CharField(
        "murojaat matni", max_length=300, blank=True, help_text="«Rahmat» sahifasida rasm yonida chiqadi"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "OTM"
        verbose_name_plural = "OTMlar"
        ordering = ["name"]

    def __str__(self):
        return f"{self.short_name} · {self.name}"

    @property
    def plan_info(self) -> dict:
        return plans.PLANS.get(self.plan, plans.PLANS["pilot"])

    def has_feature(self, feature: str) -> bool:
        return feature in self.plan_info["features"]

    @property
    def student_limit(self):
        return self.plan_info["students"]

    @property
    def brand_name(self) -> str:
        return f"{self.short_name} Talent Hub"

    @property
    def is_default(self) -> bool:
        return self.slug == settings.DEFAULT_INSTITUTION_SLUG

    @property
    def initials(self) -> str:
        letters = re.sub(r"[^A-Za-z0-9]", "", self.short_name)
        return (letters[:4] or "OTM").upper()

    def base_url(self, request=None) -> str:
        """OTM saytining manzili (Telegram tugmalari, QR kodlar uchun)."""
        if self.domain:
            return f"https://{self.domain}"
        if settings.SAAS_BASE_DOMAIN:
            return f"https://{self.slug}.{settings.SAAS_BASE_DOMAIN}"
        if request is not None:
            hostname, _, port = request.get_host().partition(":")
            if hostname in ("localhost", "127.0.0.1") or hostname.endswith(".localhost"):
                # Lokal sinov: har bir OTM o'z <manzil>.localhost subdomenida
                name = "localhost" if self.is_default else f"{self.slug}.localhost"
                return f"{request.scheme}://{name}{':' + port if port else ''}"
            return request.build_absolute_uri("/").rstrip("/")
        return settings.SITE_URL.rstrip("/")


class InstitutionRequest(models.Model):
    """«OTMingizni ulang» sahifasidan kelgan ariza."""

    class Status(models.TextChoices):
        NEW = "new", "Yangi"
        APPROVED = "approved", "Tasdiqlangan"
        REJECTED = "rejected", "Rad etilgan"

    institution_name = models.CharField("OTM nomi", max_length=200)
    short_name = models.CharField("qisqa nomi", max_length=20)
    contact_name = models.CharField("F.I.Sh.", max_length=200)
    position = models.CharField("lavozimi", max_length=120, blank=True)
    phone = models.CharField("telefon", max_length=30)
    email = models.EmailField("email", blank=True)
    students = models.PositiveIntegerField("talabalar soni (taxminan)", null=True, blank=True)
    plan = models.CharField("qiziqtirgan tarif", max_length=20, choices=plans.CHOICES, default="pilot")
    message = models.TextField("izoh", blank=True)
    status = models.CharField("holat", max_length=20, choices=Status.choices, default=Status.NEW)
    institution = models.ForeignKey(
        Institution, null=True, blank=True, on_delete=models.SET_NULL, related_name="+", verbose_name="yaratilgan OTM"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "ulanish arizasi"
        verbose_name_plural = "ulanish arizalari"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.institution_name} ({self.get_status_display()})"
