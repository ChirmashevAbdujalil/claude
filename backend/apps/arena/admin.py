from django.contrib import admin, messages

from . import services
from .models import Badge, PointTransaction, Streak, UserBadge


@admin.register(PointTransaction)
class PointTransactionAdmin(admin.ModelAdmin):
    list_display = ["user", "xp", "coins", "reason", "note", "created_at"]
    list_filter = ["reason", "created_at"]
    search_fields = ["user__username", "user__first_name", "user__last_name", "ref"]
    autocomplete_fields = ["user"]

    def get_readonly_fields(self, request, obj=None):
        # Jurnal o'zgarmas: mavjud yozuvlarni tahrirlab bo'lmaydi
        if obj is not None:
            return [f.name for f in self.model._meta.fields]
        return ["reason", "ref"]

    def has_delete_permission(self, request, obj=None):
        return False

    def save_model(self, request, obj, form, change):
        # Admin orqali faqat qo'lda ball berish mumkin; foydalanuvchi qiymatlari ham yangilanadi
        tx = services.award(obj.user, services.Reason.MANUAL, obj.xp, coins=obj.coins, note=obj.note)
        obj.pk = tx.pk
        messages.info(request, f"{obj.user} ga {obj.xp} XP berildi")


@admin.register(Badge)
class BadgeAdmin(admin.ModelAdmin):
    list_display = ["icon", "name", "code", "xp_bonus"]
    search_fields = ["name", "code"]


@admin.register(UserBadge)
class UserBadgeAdmin(admin.ModelAdmin):
    list_display = ["user", "badge", "awarded_at"]
    list_filter = ["badge"]
    autocomplete_fields = ["user"]


@admin.register(Streak)
class StreakAdmin(admin.ModelAdmin):
    list_display = ["user", "current", "longest", "last_active"]
    readonly_fields = ["current", "longest", "last_active"]
