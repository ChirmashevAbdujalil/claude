from django.contrib import admin

from .models import ClickTransaction, Invoice, PaymeTransaction


class PlatformOnlyAdmin(admin.ModelAdmin):
    """To'lovlar faqat platforma egasiga ko'rinadi."""

    def has_module_permission(self, request):
        return request.user.is_superuser

    def has_view_permission(self, request, obj=None):
        return request.user.is_superuser


@admin.register(Invoice)
class InvoiceAdmin(PlatformOnlyAdmin):
    list_display = ["id", "institution", "plan", "months", "amount", "status", "provider", "created_at", "paid_at"]
    list_filter = ["status", "provider", "plan"]
    search_fields = ["institution__name", "institution__short_name"]
    readonly_fields = ["status", "provider", "paid_at", "previous_plan", "previous_paid_until", "new_paid_until"]


@admin.register(PaymeTransaction)
class PaymeTransactionAdmin(PlatformOnlyAdmin):
    list_display = ["payme_id", "invoice", "amount", "state", "reason", "create_time", "perform_time"]
    list_filter = ["state"]
    search_fields = ["payme_id"]

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(ClickTransaction)
class ClickTransactionAdmin(PlatformOnlyAdmin):
    list_display = ["click_trans_id", "invoice", "amount", "state", "error", "created_at"]
    list_filter = ["state"]
    search_fields = ["click_trans_id"]

    def has_change_permission(self, request, obj=None):
        return False
