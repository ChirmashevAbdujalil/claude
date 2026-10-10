from django.contrib import admin

from .models import Comment, Event, EventRegistration, Post


@admin.register(Post)
class PostAdmin(admin.ModelAdmin):
    list_display = ["author", "short_text", "is_hidden", "created_at"]
    list_filter = ["is_hidden"]
    list_editable = ["is_hidden"]
    search_fields = ["text", "author__username"]
    exclude = ["likes"]

    @admin.display(description="matn")
    def short_text(self, obj):
        return obj.text[:60]


@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = ["author", "post", "text", "created_at"]
    search_fields = ["text"]


class RegistrationInline(admin.TabularInline):
    model = EventRegistration
    extra = 0
    readonly_fields = ["user", "registered_at", "attended_at"]


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ["title", "location", "starts_at", "ends_at", "xp_reward", "checkin_code"]
    readonly_fields = ["checkin_code"]
    exclude = ["created_by"]
    inlines = [RegistrationInline]

    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)
