from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UserCreationForm
from django.db import models

from apps.ai.models import Conversation
from apps.community.models import Comment, Event, Post
from apps.discovery.models import Challenge, TalentFlag
from apps.opportunities.models import Opportunity
from apps.profiles.models import Achievement, Skill, UserSkill
from apps.projects.models import Project

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
