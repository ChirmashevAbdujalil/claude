from django.contrib import admin

from .models import Achievement, Endorsement, Skill, UserSkill


@admin.register(Skill)
class SkillAdmin(admin.ModelAdmin):
    list_display = ["name", "category"]
    list_filter = ["category"]
    search_fields = ["name"]


@admin.register(UserSkill)
class UserSkillAdmin(admin.ModelAdmin):
    list_display = ["user", "skill", "level"]
    list_filter = ["skill__category"]
    autocomplete_fields = ["user", "skill"]


@admin.register(Endorsement)
class EndorsementAdmin(admin.ModelAdmin):
    list_display = ["user_skill", "endorsed_by", "created_at"]


@admin.register(Achievement)
class AchievementAdmin(admin.ModelAdmin):
    list_display = ["title", "user", "kind", "status", "xp_awarded", "achieved_on"]
    list_filter = ["status", "kind"]
    search_fields = ["title", "user__username", "user__last_name"]
    readonly_fields = ["status", "reviewed_by", "xp_awarded"]
    autocomplete_fields = ["user"]
