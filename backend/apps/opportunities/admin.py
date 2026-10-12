from django.contrib import admin
from django.db.models import Count, Q, Sum

from apps.tenants.admin import TenantAdminMixin

from .models import Application, Opportunity, Redemption, Reward, Sponsor


@admin.register(Opportunity)
class OpportunityAdmin(TenantAdminMixin, admin.ModelAdmin):
    list_display = ["title", "kind", "organization", "min_level", "deadline", "is_active"]
    list_filter = ["kind", "is_active"]
    search_fields = ["title", "organization"]
    exclude = ["created_by"]

    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(Application)
class ApplicationAdmin(admin.ModelAdmin):
    list_display = ["user", "opportunity", "status", "created_at"]
    list_filter = ["status", "opportunity__kind"]
    list_editable = ["status"]


@admin.register(Sponsor)
class SponsorAdmin(TenantAdminMixin, admin.ModelAdmin):
    list_display = ["name", "is_active", "order", "reward_count", "delivered", "coins_value"]
    list_editable = ["is_active", "order"]
    prepopulated_fields = {"slug": ["name"]}
    search_fields = ["name"]

    def get_queryset(self, request):
        given = Q(rewards__redemptions__isnull=False)
        return (
            super()
            .get_queryset(request)
            .annotate(
                n_rewards=Count("rewards", distinct=True),
                n_given=Count("rewards__redemptions", distinct=True),
                value=Sum("rewards__redemptions__price", filter=given),
            )
        )

    @admin.display(description="sovg'alar", ordering="n_rewards")
    def reward_count(self, obj):
        return obj.n_rewards

    @admin.display(description="berilgan", ordering="n_given")
    def delivered(self, obj):
        return obj.n_given

    @admin.display(description="tanga qiymati", ordering="value")
    def coins_value(self, obj):
        return obj.value or 0


@admin.register(Reward)
class RewardAdmin(TenantAdminMixin, admin.ModelAdmin):
    list_display = ["emoji", "name", "price", "stock", "sponsor", "is_active"]
    list_display_links = ["emoji", "name"]
    list_editable = ["price", "stock", "is_active"]
    list_filter = ["sponsor", "is_active"]
    autocomplete_fields = ["sponsor"]


@admin.register(Redemption)
class RedemptionAdmin(admin.ModelAdmin):
    list_display = ["user", "reward", "price", "status", "created_at"]
    list_filter = ["status"]
    list_editable = ["status"]
    readonly_fields = ["user", "reward", "price"]
