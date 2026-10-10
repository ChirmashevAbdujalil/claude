from django.contrib import admin

from .models import Conversation, Message


class MessageInline(admin.TabularInline):
    model = Message
    extra = 0
    readonly_fields = ["role", "content", "input_tokens", "output_tokens", "created_at"]
    can_delete = False


@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    list_display = ["__str__", "user", "mode", "updated_at"]
    list_filter = ["mode"]
    readonly_fields = ["user", "mode", "title"]
    inlines = [MessageInline]
