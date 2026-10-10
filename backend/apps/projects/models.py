from django.conf import settings
from django.db import models

from apps.profiles.models import Skill


class Project(models.Model):
    class Stage(models.TextChoices):
        IDEA = "idea", "G'oya"
        PROTOTYPE = "prototype", "Prototip"
        TESTING = "testing", "Sinov"
        STARTUP = "startup", "Startup"

    STAGE_ORDER = [Stage.IDEA, Stage.PROTOTYPE, Stage.TESTING, Stage.STARTUP]

    title = models.CharField("nomi", max_length=200)
    description = models.TextField("tavsif")
    problem = models.TextField("qanday muammoni hal qiladi", blank=True)
    stage = models.CharField("bosqich", max_length=20, choices=Stage.choices, default=Stage.IDEA)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="owned_projects")
    skills_needed = models.ManyToManyField(
        Skill, blank=True, related_name="projects", verbose_name="kerakli ko'nikmalar"
    )
    repo_url = models.URLField("repozitoriy", blank=True)
    demo_url = models.URLField("demo", blank=True)
    is_recruiting = models.BooleanField("jamoa a'zosi qidirilmoqda", default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "loyiha"
        verbose_name_plural = "loyihalar"
        ordering = ["-updated_at"]

    def __str__(self):
        return self.title

    @property
    def next_stage(self):
        index = self.STAGE_ORDER.index(self.stage)
        return self.STAGE_ORDER[index + 1] if index + 1 < len(self.STAGE_ORDER) else None


class ProjectMember(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "So'rov yuborilgan"
        ACTIVE = "active", "A'zo"

    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="members")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="project_memberships")
    role = models.CharField("vazifasi", max_length=100, default="A'zo")
    message = models.CharField("xabar", max_length=500, blank=True)
    status = models.CharField("holat", max_length=10, choices=Status.choices, default=Status.PENDING)
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "loyiha a'zosi"
        verbose_name_plural = "loyiha a'zolari"
        constraints = [models.UniqueConstraint(fields=["project", "user"], name="unique_project_member")]

    def __str__(self):
        return f"{self.user} @ {self.project}"
