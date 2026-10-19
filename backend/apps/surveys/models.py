import secrets

from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.tenants.context import default_institution_id
from apps.tenants.managers import TenantManager


def new_token() -> str:
    return secrets.token_urlsafe(6)


class Survey(models.Model):
    """Google Forms kabi so'rovnoma: rahbariyat tuzadi, talabalar havola yoki QR orqali javob beradi."""

    class Status(models.TextChoices):
        DRAFT = "draft", "Qoralama"
        OPEN = "open", "Javob qabul qilinmoqda"
        CLOSED = "closed", "Yopilgan"

    class Access(models.TextChoices):
        PUBLIC = "public", "Havolasi bor hamma (kirish shart emas)"
        STUDENTS = "students", "Faqat platformaga kirgan talabalar"

    institution = models.ForeignKey(
        "tenants.Institution",
        on_delete=models.CASCADE,
        related_name="surveys",
        default=default_institution_id,
        verbose_name="OTM",
    )
    title = models.CharField("nomi", max_length=200)
    description = models.TextField("tavsif", blank=True)
    token = models.CharField("ochiq havola kaliti", max_length=16, unique=True, default=new_token, editable=False)
    status = models.CharField("holat", max_length=10, choices=Status.choices, default=Status.DRAFT, db_index=True)
    access = models.CharField("kim javob bera oladi", max_length=10, choices=Access.choices, default=Access.PUBLIC)
    collect_identity = models.BooleanField(
        "talaba ma'lumotlarini so'rash",
        default=True,
        help_text="F.I.Sh., fakultet, kurs, guruh va telefon. Platformaga kirgan talabada o'zi to'ldiriladi",
    )
    one_response = models.BooleanField("har kim bir marta javob beradi", default=True)
    talent_census = models.BooleanField(
        "iqtidorlarni ro'yxatga olish",
        default=False,
        help_text="Javob bergan talabalarni natijalar sahifasidan bir bosishda iqtidorlar reyestriga qo'shish mumkin",
    )
    xp_reward = models.PositiveSmallIntegerField(
        "javob uchun XP", default=0, help_text="Platformaga kirib javob bergan talabaga bir marta beriladi"
    )
    closes_at = models.DateTimeField("javob qabul qilish muddati", null=True, blank=True)
    thank_you = models.CharField("javobdan keyingi xabar", max_length=300, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+", verbose_name="muallif"
    )
    published_at = models.DateTimeField("e'lon qilingan", null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = TenantManager()

    class Meta:
        verbose_name = "so'rovnoma"
        verbose_name_plural = "so'rovnomalar"
        ordering = ["-created_at"]

    def __str__(self):
        return self.title

    @property
    def is_expired(self) -> bool:
        return self.closes_at is not None and self.closes_at <= timezone.now()

    @property
    def is_accepting(self) -> bool:
        return self.status == self.Status.OPEN and not self.is_expired


class Question(models.Model):
    tenant_path = "survey__institution"

    class Kind(models.TextChoices):
        SHORT = "short", "Qisqa javob"
        LONG = "long", "Batafsil javob"
        SINGLE = "single", "Bitta variant"
        MULTIPLE = "multiple", "Bir nechta variant"
        DROPDOWN = "dropdown", "Ro'yxatdan tanlash"
        SCALE = "scale", "Baholash shkalasi"
        NUMBER = "number", "Raqam"
        DATE = "date", "Sana"
        EMAIL = "email", "Elektron pochta"
        PHONE = "phone", "Telefon raqam"
        TRACK = "track", "Iqtidor yo'nalishi"
        SECTION = "section", "Bo'lim sarlavhasi"

    CHOICE_KINDS = {Kind.SINGLE, Kind.MULTIPLE, Kind.DROPDOWN}
    TEXT_KINDS = {Kind.SHORT, Kind.LONG, Kind.EMAIL, Kind.PHONE, Kind.DATE}

    survey = models.ForeignKey(Survey, on_delete=models.CASCADE, related_name="questions")
    order = models.PositiveSmallIntegerField("tartib", default=0)
    kind = models.CharField("turi", max_length=10, choices=Kind.choices, default=Kind.SHORT)
    title = models.CharField("savol", max_length=300)
    help_text = models.CharField("izoh", max_length=300, blank=True)
    required = models.BooleanField("majburiy", default=False)
    options = models.JSONField("variantlar", default=list, blank=True)
    allow_other = models.BooleanField("«Boshqa» varianti", default=False)
    scale_max = models.PositiveSmallIntegerField("shkala chegarasi", default=5)
    scale_min_label = models.CharField("shkala boshi", max_length=40, blank=True)
    scale_max_label = models.CharField("shkala oxiri", max_length=40, blank=True)

    objects = TenantManager()

    class Meta:
        verbose_name = "savol"
        verbose_name_plural = "savollar"
        ordering = ["order", "id"]

    def __str__(self):
        return self.title

    @property
    def is_answerable(self) -> bool:
        return self.kind != self.Kind.SECTION

    @property
    def choices(self) -> list[tuple[str, str]]:
        """(qiymat, matn) juftliklari: tanlov va yo'nalish savollari uchun."""
        if self.kind == self.Kind.TRACK:
            from apps.talent.tracks import Track

            return list(Track.choices)
        if self.kind == self.Kind.SCALE:
            return [(str(n), str(n)) for n in range(1, self.scale_max + 1)]
        return [(option, option) for option in self.options]


class Response(models.Model):
    tenant_path = "survey__institution"

    survey = models.ForeignKey(Survey, on_delete=models.CASCADE, related_name="responses")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="survey_responses",
        verbose_name="foydalanuvchi",
    )
    full_name = models.CharField("F.I.Sh.", max_length=150, blank=True)
    faculty = models.ForeignKey(
        "accounts.Faculty", null=True, blank=True, on_delete=models.SET_NULL, related_name="+", verbose_name="fakultet"
    )
    course = models.PositiveSmallIntegerField("kurs", null=True, blank=True)
    group = models.CharField("guruh", max_length=40, blank=True)
    phone = models.CharField("telefon", max_length=30, blank=True)
    answers = models.JSONField("javoblar", default=dict)
    browser_key = models.CharField(max_length=32, blank=True, db_index=True, editable=False)
    submitted_at = models.DateTimeField("yuborilgan", default=timezone.now, db_index=True)

    objects = TenantManager()

    class Meta:
        verbose_name = "javob"
        verbose_name_plural = "javoblar"
        ordering = ["-submitted_at", "-id"]

    def __str__(self):
        return f"{self.survey}: {self.display_name}"

    @property
    def display_name(self) -> str:
        if self.full_name:
            return self.full_name
        if self.user_id:
            return str(self.user)
        return "Anonim"
