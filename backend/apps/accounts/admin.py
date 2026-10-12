from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.db import models

from apps.tenants.admin import TenantAdminMixin

from .models import Faculty, User


@admin.register(Faculty)
class FacultyAdmin(TenantAdminMixin, admin.ModelAdmin):
    list_display = ["name", "short_name"]
    search_fields = ["name", "short_name"]


@admin.register(User)
class UserAdmin(TenantAdminMixin, BaseUserAdmin):
    list_display = ["username", "first_name", "last_name", "role", "faculty", "course", "xp", "coins"]
    list_filter = ["role", "faculty", "course", "is_active"]
    search_fields = ["username", "first_name", "last_name", "telegram_id"]
    readonly_fields = ["xp", "coins"]
    formfield_overrides = {models.URLField: {"assume_scheme": "https"}}
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
    # OTM administratori uchun: huquqlarni (superuser, guruhlar) o'zgartira olmaydi
    limited_fieldsets = (
        (None, {"fields": ("username", "password")}),
        ("Shaxsiy ma'lumotlar", {"fields": ("first_name", "last_name", "email", "is_active")}),
        fieldsets[-1],
    )

    def get_fieldsets(self, request, obj=None):
        if obj is None:
            return super().get_fieldsets(request, obj)
        if not request.user.is_superuser:
            return self.limited_fieldsets
        main = self.fieldsets[:-1]
        name, options = self.fieldsets[-1]
        return (*main, (name, {"fields": ("institution", *options["fields"])}))
