from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import Faculty, User


@admin.register(Faculty)
class FacultyAdmin(admin.ModelAdmin):
    list_display = ["name", "short_name"]
    search_fields = ["name", "short_name"]


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ["username", "first_name", "last_name", "role", "faculty", "course", "xp", "coins"]
    list_filter = ["role", "faculty", "course", "is_active"]
    search_fields = ["username", "first_name", "last_name", "telegram_id"]
    readonly_fields = ["xp", "coins"]
    fieldsets = BaseUserAdmin.fieldsets + (
        (
            "Talent Hub",
            {
                "fields": (
                    "role",
                    "telegram_id",
                    "faculty",
                    "course",
                    "bio",
                    "avatar",
                    "github_url",
                    "linkedin_url",
                    "portfolio_slug",
                    "is_public",
                    "xp",
                    "coins",
                )
            },
        ),
    )
