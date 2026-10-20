import secrets

from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.tenants.context import default_institution_id
from apps.tenants.managers import TenantManager


def new_token() -> str:
    return secrets.token_urlsafe(6)


class Survey(models.Model):
    """Google Forms kabi so'rovnoma: rahbariyat tuzadi, har qanday talaba havola yoki QR orqali javob beradi.

    Javob berish uchun ro'yxatdan o'tish shart emas; platformaga kirgan talabaning javobi profiliga bog'lanadi.
    """

    class Status(models.TextChoices):
        DRAFT = "draft", "Qoralama"
        OPEN = "open", "Javob qabul qilinmoqda"
        CLOSED = "closed", "Yopilgan"

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
    create_accounts = models.BooleanField(
        "javob berganlarga akkaunt ochish",
        default=True,
        help_text="Platformada akkaunti yo'q talabaga login va parol avtomatik yaratiladi. "
        "Ular «Login va parollar» sahifasida chiqadi",
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
    tutor = models.ForeignKey(
        "accounts.Tutor",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="responses",
        verbose_name="tyutor",
    )
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


class IssuedAccount(models.Model):
    """So'rovnoma javobidan avtomatik ochilgan talaba akkaunti va uning boshlang'ich paroli.

    Boshlang'ich parol rahbariyat talabaga berishi uchun faqat talaba birinchi marta kirguncha saqlanadi:
    birinchi kirishda o'chiriladi va talaba o'z parolini o'rnatadi.
    """

    tenant_path = "user__institution"

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="issued_account", verbose_name="talaba"
    )
    survey = models.ForeignKey(
        Survey,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="issued_accounts",
        verbose_name="so'rovnoma",
    )
    initial_password = models.CharField("boshlang'ich parol", max_length=40, blank=True)
    must_change_password = models.BooleanField("parolni almashtirishi kerak", default=True)
    group = models.CharField("guruh", max_length=40, blank=True)
    tutor = models.ForeignKey(
        "accounts.Tutor",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="issued_accounts",
        verbose_name="tyutor",
    )
    phone = models.CharField("telefon", max_length=30, blank=True)
    phone_key = models.CharField(max_length=15, blank=True, db_index=True, editable=False)
    created_at = models.DateTimeField("ochilgan", default=timezone.now, db_index=True)
    first_login_at = models.DateTimeField("birinchi kirgan", null=True, blank=True)

    objects = TenantManager()

    class Meta:
        verbose_name = "ochilgan akkaunt"
        verbose_name_plural = "so'rovnomadan ochilgan akkauntlar"
        ordering = ["-created_at", "-id"]

    def __str__(self):
        return str(self.user)

    @property
    def is_waiting(self) -> bool:
        """Talaba hali kirmagan: boshlang'ich parol berilishi kerak."""
        return bool(self.initial_password)


class Club(models.Model):
    """So'rovnomada bir xil javob bergan (masalan, bir yo'nalish yoki ko'nikmani tanlagan) talabalar klubi."""

    tenant_path = "survey__institution"

    survey = models.ForeignKey(Survey, on_delete=models.CASCADE, related_name="clubs", verbose_name="so'rovnoma")
    question = models.ForeignKey(
        Question, null=True, blank=True, on_delete=models.SET_NULL, related_name="clubs", verbose_name="savol"
    )
    option = models.CharField("javob varianti", max_length=300)
    name = models.CharField("nomi", max_length=120)
    emoji = models.CharField("belgi", max_length=8, default="🧩")
    description = models.TextField("tavsif", blank=True)
    leader = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+",
        verbose_name="sardor",
    )  # fmt: skip
    mentor = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+",
        verbose_name="mentor",
    )  # fmt: skip
    telegram_url = models.URLField("Telegram guruh havolasi", blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = TenantManager()

    class Meta:
        verbose_name = "klub"
        verbose_name_plural = "klublar"
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(fields=["survey", "question", "option"], name="club_unique_option_per_question")
        ]

    def __str__(self):
        return self.name


class ClubMember(models.Model):
    tenant_path = "club__survey__institution"

    club = models.ForeignKey(Club, on_delete=models.CASCADE, related_name="members", verbose_name="klub")
    response = models.ForeignKey(
        Response, on_delete=models.CASCADE, related_name="club_memberships", verbose_name="javob"
    )
    joined_at = models.DateTimeField(default=timezone.now)

    objects = TenantManager()

    class Meta:
        verbose_name = "klub a'zosi"
        verbose_name_plural = "klub a'zolari"
        ordering = ["response__full_name"]
        constraints = [models.UniqueConstraint(fields=["club", "response"], name="club_member_unique")]

    def __str__(self):
        return f"{self.club}: {self.response.display_name}"
