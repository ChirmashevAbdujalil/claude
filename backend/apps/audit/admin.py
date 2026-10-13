from django.contrib import admin

from apps.tenants.admin import TenantAdminMixin

from .models import AuditLog


@admin.register(AuditLog)
class AuditLogAdmin(TenantAdminMixin, admin.ModelAdmin):
    """Faqat ko'rish: jurnal yozuvlarini qo'shish, o'zgartirish va o'chirish mumkin emas."""

    list_display = ["created_at", "actor_repr", "actor_role", "action", "target_label", "target_repr", "ip"]
    list_filter = ["action", "target_label", "created_at"]
    search_fields = ["actor_repr", "target_repr", "ip"]
    date_hierarchy = "created_at"
    readonly_fields = [f.name for f in AuditLog._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
