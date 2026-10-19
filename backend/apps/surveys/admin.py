from django.contrib import admin

from apps.tenants.admin import TenantAdminMixin

from .models import IssuedAccount, Question, Response, Survey


class QuestionInline(admin.StackedInline):
    model = Question
    extra = 0
    fields = [("order", "kind", "required"), "title", "help_text", "options", "allow_other"]


@admin.register(Survey)
class SurveyAdmin(TenantAdminMixin, admin.ModelAdmin):
    list_display = ["title", "status", "talent_census", "closes_at", "created_by", "created_at"]
    list_filter = ["status", "talent_census"]
    search_fields = ["title", "description"]
    readonly_fields = ["token", "published_at", "created_by"]
    inlines = [QuestionInline]

    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ["title", "survey", "kind", "required", "order"]
    list_filter = ["kind"]
    search_fields = ["title", "survey__title"]


@admin.register(Response)
class ResponseAdmin(admin.ModelAdmin):
    list_display = ["survey", "display_name", "faculty", "course", "user", "submitted_at"]
    list_filter = ["survey", "faculty"]
    search_fields = ["full_name", "user__username", "phone"]
    readonly_fields = ["survey", "user", "answers", "submitted_at"]


@admin.register(IssuedAccount)
class IssuedAccountAdmin(admin.ModelAdmin):
    list_display = ["user", "survey", "group", "phone", "created_at", "first_login_at", "must_change_password"]
    list_filter = ["must_change_password", "survey"]
    search_fields = ["user__username", "user__first_name", "user__last_name", "phone", "group"]
    readonly_fields = ["user", "survey", "initial_password", "created_at", "first_login_at"]
