from django.contrib import admin

from apps.tenants.admin import TenantAdminMixin

from .models import DevelopmentGoal, DiagnosticResult, TalentProfile


class GoalInline(admin.TabularInline):
    model = DevelopmentGoal
    extra = 0
    fields = ["title", "kind", "due_date", "status", "progress", "mentor_comment"]


@admin.register(TalentProfile)
class TalentProfileAdmin(TenantAdminMixin, admin.ModelAdmin):
    list_display = ["student", "track", "status", "mentor", "source", "created_at"]
    list_filter = ["status", "track", "source"]
    search_fields = ["student__username", "student__first_name", "student__last_name"]
    autocomplete_fields = ["student", "mentor"]
    inlines = [GoalInline]


@admin.register(DiagnosticResult)
class DiagnosticResultAdmin(TenantAdminMixin, admin.ModelAdmin):
    list_display = ["user", "track", "second_track", "taken_at"]
    list_filter = ["track"]
    readonly_fields = ["answers", "scores"]
