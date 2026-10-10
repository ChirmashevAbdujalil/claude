from rest_framework import serializers

from .models import Badge, PointTransaction, Streak, UserBadge


class BadgeSerializer(serializers.ModelSerializer):
    earned = serializers.SerializerMethodField()

    class Meta:
        model = Badge
        fields = ["code", "name", "description", "icon", "xp_bonus", "earned"]

    def get_earned(self, obj) -> bool:
        return obj.code in self.context.get("earned_codes", set())


class UserBadgeSerializer(serializers.ModelSerializer):
    code = serializers.CharField(source="badge.code")
    name = serializers.CharField(source="badge.name")
    icon = serializers.CharField(source="badge.icon")

    class Meta:
        model = UserBadge
        fields = ["code", "name", "icon", "awarded_at"]


class StreakSerializer(serializers.ModelSerializer):
    class Meta:
        model = Streak
        fields = ["current", "longest", "last_active"]


class PointTransactionSerializer(serializers.ModelSerializer):
    reason_display = serializers.CharField(source="get_reason_display")

    class Meta:
        model = PointTransaction
        fields = ["id", "xp", "coins", "reason", "reason_display", "note", "created_at"]


class LeaderboardEntrySerializer(serializers.Serializer):
    rank = serializers.IntegerField()
    user_id = serializers.IntegerField()
    full_name = serializers.CharField()
    faculty = serializers.CharField(allow_null=True)
    course = serializers.IntegerField(allow_null=True)
    xp = serializers.IntegerField()


class LeagueEntrySerializer(serializers.Serializer):
    rank = serializers.IntegerField()
    faculty_id = serializers.IntegerField()
    faculty = serializers.CharField()
    xp = serializers.IntegerField()
    members = serializers.IntegerField()
