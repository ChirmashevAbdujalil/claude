from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UserCreationForm
from django.db import models

from apps.accounts.models import Faculty
from apps.ai.models import Conversation
from apps.community.models import Comment, Event, Post
from apps.discovery.models import Challenge, TalentFlag
from apps.opportunities.models import Opportunity
from apps.profiles.models import Achievement, Resume, Skill, UserSkill
from apps.projects.models import Project
from apps.surveys import services as survey_services
from apps.surveys.models import Survey
from apps.talent.models import DevelopmentGoal, TalentProfile
from apps.talent.tracks import Track
from apps.tenants.models import Institution, InstitutionRequest

User = get_user_model()


def https_urls(field, **kwargs):
    """URL maydonlarida sxema yozilmasa https deb hisoblanadi."""
    if isinstance(field, models.URLField):
        kwargs.setdefault("assume_scheme", "https")
    return field.formfield(**kwargs)


DATETIME_WIDGET = forms.DateTimeInput(attrs={"type": "datetime-local"}, format="%Y-%m-%dT%H:%M")
DATE_WIDGET = forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d")


class LoginForm(forms.Form):
    username = forms.CharField(
        label="Login", max_length=150, widget=forms.TextInput(attrs={"autocomplete": "username"})
    )
    password = forms.CharField(label="Parol", widget=forms.PasswordInput(attrs={"autocomplete": "current-password"}))


class RegisterForm(UserCreationForm):
    first_name = forms.CharField(label="Ism", max_length=150)
    last_name = forms.CharField(label="Familiya", max_length=150)

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ["first_name", "last_name", "username"]
        labels = {"username": "Login"}
        help_texts = {"username": "Lotin harflari, raqamlar va @ . + - _ belgilari. Masalan: aziz_karimov"}

    def save(self, commit=True):
        user = super().save(commit=False)
        user.role = User.Role.STUDENT
        if commit:
            user.save()
        return user


class OnboardingProfileForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ["faculty", "course"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["faculty"].required = True
        self.fields["faculty"].empty_label = "Fakultetni tanlang"
        self.fields["course"].required = True
        self.fields["course"].widget = forms.Select(
            choices=[("", "Kursni tanlang")] + [(i, f"{i}-kurs") for i in range(1, 7)]
        )

    def clean_course(self):
        course = self.cleaned_data.get("course")
        if course is not None and not 1 <= course <= 6:
            raise forms.ValidationError("Kurs 1 dan 6 gacha bo'lishi kerak")
        return course


class ProfileForm(forms.ModelForm):
    class Meta:
        model = User
        formfield_callback = https_urls
        fields = [
            "first_name",
            "last_name",
            "faculty",
            "course",
            "bio",
            "avatar",
            "github_url",
            "linkedin_url",
            "portfolio_slug",
            "is_public",
        ]
        labels = {"first_name": "Ism", "last_name": "Familiya"}
        widgets = {"bio": forms.Textarea(attrs={"rows": 4, "placeholder": "Nimalarga qiziqasiz, nimani o'rganyapsiz?"})}
        help_texts = {"portfolio_slug": "Portfolio sahifangiz manzili, masalan: aziz-karimov"}

    def clean_course(self):
        course = self.cleaned_data.get("course")
        if course is not None and not 1 <= course <= 6:
            raise forms.ValidationError("Kurs 1 dan 6 gacha bo'lishi kerak")
        return course


class UserSkillForm(forms.ModelForm):
    level = forms.TypedChoiceField(
        label="Daraja",
        coerce=int,
        choices=[(1, "1 · Boshlang'ich"), (2, "2"), (3, "3 · O'rta"), (4, "4"), (5, "5 · Ekspert")],
        initial=2,
    )

    class Meta:
        model = UserSkill
        fields = ["skill", "level"]

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        taken = UserSkill.objects.filter(user=user).values_list("skill_id", flat=True) if user else []
        self.fields["skill"].queryset = Skill.objects.exclude(pk__in=taken)
        self.fields["skill"].empty_label = "Ko'nikmani tanlang"


class AchievementForm(forms.ModelForm):
    class Meta:
        model = Achievement
        formfield_callback = https_urls
        fields = ["kind", "title", "achieved_on", "description", "proof", "proof_url"]
        widgets = {"achieved_on": DATE_WIDGET, "description": forms.Textarea(attrs={"rows": 3})}

    def clean(self):
        data = super().clean()
        if not data.get("proof") and not data.get("proof_url"):
            raise forms.ValidationError("Tasdiqlovchi hujjat yuklang yoki havola kiriting")
        return data


class SubmissionForm(forms.Form):
    answer = forms.CharField(
        label="Javobingiz",
        required=False,
        widget=forms.Textarea(attrs={"rows": 5, "placeholder": "Yechimingizni yozing"}),
    )
    link = forms.URLField(
        label="Havola", help_text="GitHub, Google Drive va h.k.", required=False, assume_scheme="https"
    )

    def clean(self):
        data = super().clean()
        if not (data.get("answer") or "").strip() and not data.get("link"):
            raise forms.ValidationError("Javob yoki havola kiriting")
        return data


class ChallengeForm(forms.ModelForm):
    xp_reward = forms.IntegerField(
        label="XP", required=False, min_value=0, max_value=1000, help_text="Bo'sh qolsa turiga qarab: 10 / 50 / 300"
    )

    class Meta:
        model = Challenge
        fields = [
            "title",
            "description",
            "kind",
            "difficulty",
            "category",
            "xp_reward",
            "expected_answer",
            "faculty",
            "starts_at",
            "ends_at",
            "is_published",
        ]
        widgets = {
            "starts_at": DATETIME_WIDGET,
            "ends_at": DATETIME_WIDGET,
            "description": forms.Textarea(attrs={"rows": 6}),
        }

    def clean(self):
        data = super().clean()
        if data.get("starts_at") and data.get("ends_at") and data["ends_at"] <= data["starts_at"]:
            raise forms.ValidationError("Tugash vaqti boshlanishdan keyin bo'lishi kerak")
        return data


class ReviewForm(forms.Form):
    score = forms.IntegerField(label="Baho (0-100)", required=False, min_value=0, max_value=100)
    feedback = forms.CharField(label="Izoh", required=False, widget=forms.Textarea(attrs={"rows": 2}))


class ProjectForm(forms.ModelForm):
    class Meta:
        model = Project
        formfield_callback = https_urls
        fields = ["title", "description", "problem", "skills_needed", "repo_url", "demo_url", "is_recruiting"]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 4}),
            "problem": forms.Textarea(attrs={"rows": 3}),
            "skills_needed": forms.SelectMultiple(attrs={"size": 8}),
        }
        help_texts = {"skills_needed": "Ctrl (Mac'da Cmd) tugmasini bosib bir nechtasini tanlang"}


class JoinProjectForm(forms.Form):
    role = forms.CharField(label="Qaysi vazifada ishlamoqchisiz?", max_length=100, initial="A'zo")
    message = forms.CharField(label="Xabar", required=False, max_length=500, widget=forms.Textarea(attrs={"rows": 2}))


class OpportunityForm(forms.ModelForm):
    class Meta:
        model = Opportunity
        formfield_callback = https_urls
        fields = ["kind", "title", "organization", "description", "reward", "external_url", "min_level", "deadline"]
        widgets = {"deadline": DATETIME_WIDGET, "description": forms.Textarea(attrs={"rows": 5})}

    tracks = forms.MultipleChoiceField(
        label="Qaysi iqtidor yo'nalishlariga mos?",
        choices=Track.choices,
        required=False,
        widget=forms.CheckboxSelectMultiple,
        help_text="Shu yo'nalishdagi talabalarga sayt va Telegram orqali avtomatik xabar boradi. "
        "Tanlanmasa, imkoniyat turiga qarab aniqlanadi.",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["tracks"].initial = self.instance.tracks

    def save(self, commit=True):
        self.instance.tracks = list(self.cleaned_data.get("tracks") or [])
        return super().save(commit)


class ApplyForm(forms.Form):
    motivation = forms.CharField(
        label="Motivatsiya xati",
        min_length=20,
        widget=forms.Textarea(attrs={"rows": 5, "placeholder": "Nega aynan siz? Qanday tajribangiz bor?"}),
    )


class PostForm(forms.ModelForm):
    class Meta:
        model = Post
        fields = ["text", "image"]
        widgets = {
            "text": forms.Textarea(
                attrs={"rows": 3, "placeholder": "Yutug'ingiz yoki loyihangiz bilan o'rtoqlashing..."}
            )
        }
        labels = {"text": "", "image": "Rasm"}


class CommentForm(forms.ModelForm):
    class Meta:
        model = Comment
        fields = ["text"]
        widgets = {"text": forms.Textarea(attrs={"rows": 2, "placeholder": "Izoh yozing..."})}
        labels = {"text": ""}


class EventForm(forms.ModelForm):
    class Meta:
        model = Event
        fields = ["title", "description", "location", "starts_at", "ends_at", "capacity", "xp_reward"]
        widgets = {
            "starts_at": DATETIME_WIDGET,
            "ends_at": DATETIME_WIDGET,
            "description": forms.Textarea(attrs={"rows": 4}),
        }

    def clean(self):
        data = super().clean()
        if data.get("starts_at") and data.get("ends_at") and data["ends_at"] <= data["starts_at"]:
            raise forms.ValidationError("Tugash vaqti boshlanishdan keyin bo'lishi kerak")
        return data


class TalentFlagForm(forms.ModelForm):
    class Meta:
        model = TalentFlag
        fields = ["area", "note"]
        widgets = {"note": forms.Textarea(attrs={"rows": 3, "placeholder": "Talabada nimani ko'rdingiz?"})}


class ConversationForm(forms.Form):
    mode = forms.ChoiceField(choices=Conversation.Mode.choices)


class ChatForm(forms.Form):
    text = forms.CharField(max_length=4000)


class ResumeForm(forms.ModelForm):
    """Rezyume matnlari va aloqa. Email foydalanuvchi profilida saqlanadi."""

    email = forms.EmailField(label="Email", required=False)

    class Meta:
        model = Resume
        fields = ["headline", "summary", "headline_en", "summary_en", "phone", "show_contacts_public"]
        labels = {
            "headline": "Kasbiy yo'nalish",
            "summary": "Qisqacha ma'lumot",
            "headline_en": "Headline (inglizcha)",
            "summary_en": "Profile summary (inglizcha)",
        }
        widgets = {
            "summary": forms.Textarea(
                attrs={"rows": 5, "placeholder": "Bo'sh qoldirsangiz, platforma ma'lumotlaridan avtomatik tuziladi"}
            ),
            "summary_en": forms.Textarea(
                attrs={"rows": 5, "placeholder": "Leave empty to generate from your platform data"}
            ),
            "phone": forms.TextInput(attrs={"placeholder": "+998 90 123 45 67", "inputmode": "tel"}),
            "headline_en": forms.TextInput(attrs={"placeholder": "e.g. IoT and robotics engineering student"}),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        if user is not None:
            self.fields["email"].initial = user.email

    def save(self, commit=True):
        resume = super().save(commit=commit)
        if commit and self.user is not None:
            email = self.cleaned_data.get("email", "")
            if email != self.user.email:
                self.user.email = email
                self.user.save(update_fields=["email"])
        return resume


class InstitutionRequestForm(forms.ModelForm):
    class Meta:
        model = InstitutionRequest
        fields = [
            "institution_name",
            "short_name",
            "contact_name",
            "position",
            "phone",
            "email",
            "students",
            "plan",
            "message",
        ]
        widgets = {
            "institution_name": forms.TextInput(
                attrs={"placeholder": "Masalan: Toshkent axborot texnologiyalari universiteti"}
            ),
            "short_name": forms.TextInput(attrs={"placeholder": "TATU"}),
            "phone": forms.TextInput(attrs={"placeholder": "+998 90 123 45 67", "inputmode": "tel"}),
            "message": forms.Textarea(
                attrs={"rows": 3, "placeholder": "Qaysi fakultetlardan boshlamoqchisiz, savollaringiz"}
            ),
        }


class InstitutionSettingsForm(forms.ModelForm):
    """OTM administratori uchun: nom, shior, logotip, ranglar va qoidalar."""

    class Meta:
        model = Institution
        fields = [
            "name",
            "short_name",
            "tagline",
            "logo",
            "color_dark",
            "color_light",
            "registration_open",
            "show_in_league",
        ]
        widgets = {
            "color_dark": forms.TextInput(attrs={"type": "color"}),
            "color_light": forms.TextInput(attrs={"type": "color"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.instance.has_feature("branding"):
            for name in ("logo", "color_dark", "color_light"):
                self.fields[name].disabled = True
                self.fields[name].help_text = "«Standart» va «Premium» tariflarida"


class FacultyForm(forms.ModelForm):
    class Meta:
        model = Faculty
        fields = ["name", "short_name", "contingent"]
        labels = {"name": "Fakultet nomi", "short_name": "Qisqa nomi", "contingent": "Talabalar soni"}
        widgets = {
            "name": forms.TextInput(attrs={"placeholder": "Axborot texnologiyalari fakulteti"}),
            "short_name": forms.TextInput(attrs={"placeholder": "ATF"}),
        }

    def clean(self):
        cleaned = super().clean()
        # Noyoblik OTM ichida tekshiriladi (institution maydoni formada yo'q)
        for field in ("name", "short_name"):
            value = cleaned.get(field)
            if value and Faculty.objects.filter(**{f"{field}__iexact": value}).exclude(pk=self.instance.pk).exists():
                self.add_error(field, "Bunday fakultet allaqachon bor")
        return cleaned


# ---------------------------------------------------------------- iqtidorlar bilan ishlash


class TalentAddForm(forms.Form):
    username = forms.CharField(label="Talaba logini", max_length=150, help_text="Portfolio sahifasidagi login")
    track = forms.ChoiceField(label="Yo'nalish", choices=[("", "Diagnostika bo'yicha aniqlansin")] + Track.choices,
                              required=False)  # fmt: skip
    note = forms.CharField(label="Nega iqtidorli?", required=False, widget=forms.Textarea(attrs={"rows": 2}))


class TalentMentorForm(forms.Form):
    mentor = forms.ModelChoiceField(label="Mentor", queryset=User.objects.none(), required=False,
                                    empty_label="Mentor biriktirilmagan")  # fmt: skip

    def __init__(self, *args, mentors=None, **kwargs):
        super().__init__(*args, **kwargs)
        if mentors is not None:
            self.fields["mentor"].queryset = mentors
            self.fields["mentor"].label_from_instance = lambda u: (
                f"{u.get_full_name() or u.username} · {u.get_role_display()} · {u.mentee_count} shogird"
            )


class TalentProfileForm(forms.ModelForm):
    class Meta:
        model = TalentProfile
        fields = ["track", "note"]
        widgets = {"note": forms.Textarea(attrs={"rows": 3})}


class GoalForm(forms.ModelForm):
    class Meta:
        model = DevelopmentGoal
        fields = ["title", "kind", "due_date", "status", "progress", "mentor_comment"]
        widgets = {
            "due_date": DATE_WIDGET,
            "progress": forms.NumberInput(attrs={"min": 0, "max": 100, "step": 10}),
            "title": forms.TextInput(attrs={"placeholder": "Masalan: Respublika fizika olimpiadasiga tayyorlanish"}),
        }

    def clean_progress(self):
        return max(0, min(100, self.cleaned_data["progress"] or 0))


class StudentGoalForm(forms.ModelForm):
    """Talaba o'z maqsadining holatini yangilaydi: muddat va matnni faqat mentor o'zgartiradi."""

    status = forms.ChoiceField(
        label="Holat",
        choices=[(s.value, s.label) for s in DevelopmentGoal.Status if s != DevelopmentGoal.Status.CANCELLED],
    )

    class Meta:
        model = DevelopmentGoal
        fields = ["status", "progress", "student_note"]
        widgets = {"progress": forms.NumberInput(attrs={"min": 0, "max": 100, "step": 10})}

    def clean_progress(self):
        return max(0, min(100, self.cleaned_data["progress"] or 0))


# ---------------------------------------------------------------- so'rovnomalar


class SurveyForm(forms.ModelForm):
    class Meta:
        model = Survey
        fields = [
            "title",
            "description",
            "collect_identity",
            "create_accounts",
            "one_response",
            "talent_census",
            "xp_reward",
            "closes_at",
            "thank_you",
        ]
        widgets = {
            "description": forms.Textarea(
                attrs={"rows": 3, "placeholder": "Talabalarga so'rovnoma maqsadini tushuntiring"}
            ),
            "closes_at": DATETIME_WIDGET,
            "thank_you": forms.TextInput(attrs={"placeholder": "Rahmat! Javobingiz qabul qilindi."}),
        }

    def clean_xp_reward(self):
        xp = self.cleaned_data["xp_reward"]
        if xp > survey_services.MAX_XP:
            raise forms.ValidationError(f"{survey_services.MAX_XP} XP dan oshmasin")
        return xp


class SurveyIdentityForm(forms.Form):
    """So'rovnomada talaba haqidagi umumiy ma'lumotlar (platformaga kirgan bo'lsa, o'zi to'ldiriladi)."""

    full_name = forms.CharField(label="Familiya, ism, sharif", max_length=150)
    faculty = forms.ModelChoiceField(label="Fakultet", queryset=Faculty.objects.none(), empty_label="Tanlang")
    course = forms.TypedChoiceField(
        label="Kurs", coerce=int, choices=[("", "Tanlang")] + [(n, f"{n}-kurs") for n in range(1, 7)]
    )
    group = forms.CharField(
        label="Guruh",
        max_length=20,
        help_text=f"Masalan: {survey_services.GROUP_EXAMPLE}. Harf(lar), chiziqcha, ikki raqam, chiziqcha, ikki raqam",
        widget=forms.TextInput(
            attrs={
                "placeholder": survey_services.GROUP_EXAMPLE,
                "autocapitalize": "characters",
                "autocomplete": "off",
                "spellcheck": "false",
                "data-group-input": "",
                "pattern": "[A-Za-z]{1,5}-[0-9]{2}-[0-9]{2}",
            }
        ),
    )
    phone = forms.CharField(
        label="Telefon raqam",
        max_length=30,
        required=False,
        widget=forms.TextInput(attrs={"inputmode": "tel", "placeholder": "+998 90 123 45 67"}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, prefix="who", **kwargs)
        self.fields["faculty"].queryset = Faculty.objects.order_by("name")
        if not self.fields["faculty"].queryset.exists():
            del self.fields["faculty"]

    def clean_group(self):
        group = survey_services.normalize_group(self.cleaned_data["group"])
        if not survey_services.GROUP_RE.match(group):
            raise forms.ValidationError(
                f"Guruhni {survey_services.GROUP_EXAMPLE} ko'rinishida yozing: harf(lar), chiziqcha, "
                "ikki raqam, chiziqcha, ikki raqam"
            )
        return group

    def clean_phone(self):
        phone = self.cleaned_data["phone"].strip()
        if phone and not survey_services.PHONE_RE.match(phone):
            raise forms.ValidationError("Telefon raqamini to'g'ri kiriting")
        return phone
