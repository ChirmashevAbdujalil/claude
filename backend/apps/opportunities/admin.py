from django.contrib import admin

from .models import Application, Opportunity, Redemption, Reward


@admin.register(Opportunity)
class OpportunityAdmin(admin.ModelAdmin):
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


@admin.register(Reward)
class RewardAdmin(admin.ModelAdmin):
    list_display = ["name", "price", "stock", "is_active"]
    list_editable = ["price", "stock", "is_active"]


@admin.register(Redemption)
class RedemptionAdmin(admin.ModelAdmin):
    list_display = ["user", "reward", "price", "status", "created_at"]
    list_filter = ["status"]
    list_editable = ["status"]
    readonly_fields = ["user", "reward", "price"]
