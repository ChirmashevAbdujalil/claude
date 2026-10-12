from django.contrib import admin, messages

from . import services
from .models import Institution, InstitutionRequest


class TenantAdminMixin:
    """OTMga tegishli modellar uchun: platforma egasi OTM maydonini ko'radi va filtrlaydi,
    OTM administratori esa faqat o'z OTMi bilan ishlaydi (maydon yashirin, avtomatik to'ldiriladi)."""

    def get_exclude(self, request, obj=None):
        exclude = list(super().get_exclude(request, obj) or [])
        if not request.user.is_superuser:
            exclude.append("institution")
        return exclude

    def get_list_display(self, request):
        columns = list(super().get_list_display(request))
        if request.user.is_superuser and "institution" not in columns:
            columns.append("institution")
        return columns

    def get_list_filter(self, request):
        filters = list(super().get_list_filter(request))
        if request.user.is_superuser and "institution" not in filters:
            filters.append("institution")
        return filters


@admin.register(Institution)
class InstitutionAdmin(admin.ModelAdmin):
    list_display = ["short_name", "name", "slug", "plan", "paid_until", "is_active", "created_at"]
    list_editable = ["plan", "paid_until", "is_active"]
    list_filter = ["plan", "is_active"]
    search_fields = ["name", "short_name", "slug", "domain"]
    prepopulated_fields = {"slug": ["short_name"]}
    fieldsets = [
        (None, {"fields": ["name", "short_name", "slug", "domain", "tagline"]}),
        ("Tarif", {"fields": ["plan", "paid_until", "is_active", "registration_open", "show_in_league"]}),
        ("Brend", {"fields": ["logo", "color_dark", "color_light"]}),
        ("Aloqa", {"fields": ["contact_name", "contact_phone", "contact_email"]}),
    ]

    def has_module_permission(self, request):
        return request.user.is_superuser

    def has_view_permission(self, request, obj=None):
        return request.user.is_superuser


@admin.register(InstitutionRequest)
class InstitutionRequestAdmin(admin.ModelAdmin):
    list_display = [
        "institution_name",
        "short_name",
        "contact_name",
        "phone",
        "plan",
        "students",
        "status",
        "created_at",
    ]
    list_filter = ["status", "plan"]
    search_fields = ["institution_name", "contact_name", "phone", "email"]
    readonly_fields = ["institution", "created_at"]
    actions = ["approve"]

    def has_module_permission(self, request):
        return request.user.is_superuser

    def has_view_permission(self, request, obj=None):
        return request.user.is_superuser

    @admin.action(description="Tasdiqlash: OTM va administrator hisobini yaratish")
    def approve(self, request, queryset):
        for request_obj in queryset:
            try:
                institution, admin_user, password = services.approve_request(request_obj)
            except services.TenantError as exc:
                self.message_user(request, f"{request_obj.institution_name}: {exc}", messages.ERROR)
                continue
            self.message_user(
                request,
                f"{institution.short_name} ulandi: {institution.base_url(request)} · login {admin_user.username} · "
                f"parol {password} (faqat hozir ko'rinadi)",
                messages.SUCCESS,
            )
