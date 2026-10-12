import secrets

from django.conf import settings
from django.db import models

from apps.tenants.context import default_institution_id
from apps.tenants.managers import TenantManager


def new_checkin_code() -> str:
    return secrets.token_urlsafe(16)


class Post(models.Model):
    tenant_path = "author__institution"

    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="posts")
    text = models.TextField("matn", max_length=5000)
    image = models.ImageField("rasm", upload_to="posts/", blank=True)
    project = models.ForeignKey(
        "projects.Project", null=True, blank=True, on_delete=models.SET_NULL, related_name="posts"
    )
    likes = models.ManyToManyField(settings.AUTH_USER_MODEL, blank=True, related_name="liked_posts")
    is_hidden = models.BooleanField("yashirilgan (moderatsiya)", default=False)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    objects = TenantManager()

    class Meta:
        verbose_name = "post"
        verbose_name_plural = "lenta"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.author}: {self.text[:40]}"


class Comment(models.Model):
    tenant_path = "author__institution"

    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name="comments")
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="comments")
    text = models.TextField("matn", max_length=1000)
    created_at = models.DateTimeField(auto_now_add=True)

    objects = TenantManager()

    class Meta:
        verbose_name = "izoh"
        verbose_name_plural = "izohlar"
        ordering = ["created_at"]

    def __str__(self):
        return f"{self.author}: {self.text[:40]}"


class Event(models.Model):
    institution = models.ForeignKey(
        "tenants.Institution",
        on_delete=models.CASCADE,
        related_name="events",
        default=default_institution_id,
        verbose_name="OTM",
    )
    title = models.CharField("nomi", max_length=200)
    description = models.TextField("tavsif")
    location = models.CharField("joy", max_length=200)
    starts_at = models.DateTimeField("boshlanish")
    ends_at = models.DateTimeField("tugash")
    capacity = models.PositiveIntegerField("o'rinlar soni", null=True, blank=True)
    xp_reward = models.PositiveIntegerField("XP", default=20)
    checkin_code = models.CharField(max_length=64, unique=True, default=new_checkin_code, editable=False)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)

    objects = TenantManager()

    class Meta:
        verbose_name = "tadbir"
        verbose_name_plural = "tadbirlar"
        ordering = ["starts_at"]

    def __str__(self):
        return self.title


class EventRegistration(models.Model):
    tenant_path = "user__institution"

    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name="registrations")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="event_registrations")
    registered_at = models.DateTimeField(auto_now_add=True)
    attended_at = models.DateTimeField("kelgan vaqti", null=True, blank=True)

    objects = TenantManager()

    class Meta:
        verbose_name = "ro'yxatdan o'tish"
        verbose_name_plural = "ro'yxatdan o'tganlar"
        constraints = [models.UniqueConstraint(fields=["event", "user"], name="unique_event_registration")]

    def __str__(self):
        return f"{self.user} @ {self.event}"
