from django import forms
from django.contrib import admin, messages
from django.db import models, transaction
from django.utils.text import slugify

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


class InstitutionAddForm(forms.ModelForm):
    """Yangi OTM qo'shish: OTM bilan birga uning administratori (rektorat) hisobi ham yaratiladi."""

    admin_username = forms.CharField(
        label="administrator logini",
        max_length=150,
        required=False,
        help_text="Bo'sh qoldirilsa: <manzil>_admin. Parol saqlangandan keyin bir marta ko'rsatiladi",
    )

    class Meta:
        model = Institution
        fields = [
            "name", "short_name", "slug", "domain", "tagline", "plan", "paid_until", "registration_open",
            "show_in_league", "logo", "color_dark", "color_light", "contact_name", "contact_phone", "contact_email",
        ]  # fmt: skip

    def clean_slug(self):
        slug = slugify(self.cleaned_data["slug"])
        if slug in services.RESERVED_SLUGS:
            raise forms.ValidationError(f"«{slug}» manzili band")
        return slug

    def clean(self):
        data = super().clean()
        username = data.get("admin_username") or (f"{data['slug']}_admin" if data.get("slug") else "")
        if username:
            try:
                services.check_admin_username(username)
            except services.TenantError as exc:
                self.add_error("admin_username", str(exc))
        return data


@admin.register(Institution)
class InstitutionAdmin(admin.ModelAdmin):
    list_display = ["short_name", "name", "slug", "plan", "paid_until", "is_active", "created_at"]
    list_editable = ["plan", "paid_until", "is_active"]
    list_filter = ["plan", "is_active"]
    search_fields = ["name", "short_name", "slug", "domain"]
    prepopulated_fields = {"slug": ["short_name"]}
    actions = ["reset_admin_password"]
    fieldsets = [
        (None, {"fields": ["name", "short_name", "slug", "domain", "tagline"]}),
        ("Tarif", {"fields": ["plan", "paid_until", "is_active", "registration_open", "show_in_league"]}),
        ("Brend", {"fields": ["logo", "color_dark", "color_light"]}),
        ("Aloqa", {"fields": ["contact_name", "contact_phone", "contact_email"]}),
        (
            "So'rovnomalarda mas'ul shaxs",
            {
                "fields": [
                    "curator_enabled",
                    "curator_name",
                    "curator_title",
                    "curator_photo",
                    "curator_url",
                    "curator_message",
                ]
            },
        ),
    ]
    formfield_overrides = {models.URLField: {"assume_scheme": "https"}}
    add_fieldsets = [
        (None, {"fields": ["name", "short_name", "slug", "domain", "tagline"]}),
        ("Administrator", {"fields": ["admin_username", "contact_name", "contact_phone", "contact_email"]}),
        (
            "Tarif",
            {
                "fields": ["plan", "paid_until", "registration_open", "show_in_league"],
                "description": "Pilot tarifida muddat bo'sh qoldirilsa, 90 kun qo'yiladi.",
            },
        ),
        ("Brend", {"fields": ["logo", "color_dark", "color_light"]}),
    ]

    def has_module_permission(self, request):
        return request.user.is_superuser

    def has_view_permission(self, request, obj=None):
        return request.user.is_superuser

    def get_form(self, request, obj=None, **kwargs):
        if obj is None:
            kwargs["form"] = InstitutionAddForm
        return super().get_form(request, obj, **kwargs)

    def get_fieldsets(self, request, obj=None):
        return self.add_fieldsets if obj is None else self.fieldsets

    @transaction.atomic
    def save_model(self, request, obj, form, change):
        if change:
            return super().save_model(request, obj, form, change)
        if obj.paid_until is None:
            obj.paid_until = services.pilot_until(obj.plan)
        super().save_model(request, obj, form, change)
        admin_user, password = services.create_admin(
            obj, form.cleaned_data.get("admin_username", ""), obj.contact_name, obj.contact_email
        )
        self._credentials_message(request, obj, admin_user, password, "ulandi")

    def _credentials_message(self, request, institution, admin_user, password, verb):
        self.message_user(
            request,
            f"{institution.short_name} {verb}: {institution.base_url(request)} · login {admin_user.username} · "
            f"parol {password} (faqat hozir ko'rinadi, OTMga yetkazing)",
            messages.SUCCESS,
        )

    @admin.action(description="Administrator parolini yangilash")
    def reset_admin_password(self, request, queryset):
        for institution in queryset:
            result = services.reset_admin_password(institution)
            if result is None:
                self.message_user(request, f"{institution.short_name}: administrator topilmadi", messages.WARNING)
            else:
                self._credentials_message(request, institution, *result, "paroli yangilandi")


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
