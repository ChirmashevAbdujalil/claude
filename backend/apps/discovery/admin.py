from django.contrib import admin

from apps.tenants.admin import TenantAdminMixin

from .models import Challenge, Submission, TalentFlag


@admin.register(Challenge)
class ChallengeAdmin(TenantAdminMixin, admin.ModelAdmin):
    list_display = ["title", "kind", "difficulty", "category", "xp_reward", "starts_at", "ends_at", "is_published"]
    list_filter = ["kind", "difficulty", "category", "is_published"]
    search_fields = ["title"]

    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)

    exclude = ["created_by"]


@admin.register(Submission)
class SubmissionAdmin(admin.ModelAdmin):
    list_display = ["user", "challenge", "status", "score", "xp_awarded", "created_at"]
    list_filter = ["status", "challenge__kind"]
    search_fields = ["user__username", "challenge__title"]
    readonly_fields = ["status", "xp_awarded", "reviewed_by"]


@admin.register(TalentFlag)
class TalentFlagAdmin(admin.ModelAdmin):
    list_display = ["student", "area", "flagged_by", "created_at"]
    list_filter = ["area"]
