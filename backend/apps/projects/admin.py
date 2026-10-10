from django.contrib import admin

from .models import Project, ProjectMember


class ProjectMemberInline(admin.TabularInline):
    model = ProjectMember
    extra = 0
    autocomplete_fields = ["user"]


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ["title", "owner", "stage", "is_recruiting", "updated_at"]
    list_filter = ["stage", "is_recruiting"]
    search_fields = ["title", "description"]
    filter_horizontal = ["skills_needed"]
    autocomplete_fields = ["owner"]
    inlines = [ProjectMemberInline]
