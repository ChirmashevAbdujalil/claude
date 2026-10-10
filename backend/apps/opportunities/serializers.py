from rest_framework import serializers

from apps.accounts.serializers import UserBriefSerializer

from .models import Application, Opportunity, Redemption, Reward


class OpportunitySerializer(serializers.ModelSerializer):
    kind_display = serializers.CharField(source="get_kind_display", read_only=True)
    applied = serializers.SerializerMethodField()

    class Meta:
        model = Opportunity
        fields = [
            "id",
            "kind",
            "kind_display",
            "title",
            "description",
            "organization",
            "external_url",
            "reward",
            "min_level",
            "deadline",
            "is_active",
            "applied",
            "created_at",
        ]

    def get_applied(self, obj) -> bool:
        return obj.pk in self.context.get("applied_ids", set())


class ApplySerializer(serializers.Serializer):
    motivation = serializers.CharField(min_length=20)


class ApplicationSerializer(serializers.ModelSerializer):
    user = UserBriefSerializer(read_only=True)
    opportunity_title = serializers.CharField(source="opportunity.title", read_only=True)

    class Meta:
        model = Application
        fields = ["id", "opportunity", "opportunity_title", "user", "motivation", "status", "created_at"]
        read_only_fields = ["opportunity", "motivation"]


class RewardSerializer(serializers.ModelSerializer):
    class Meta:
        model = Reward
        fields = ["id", "name", "description", "image", "price", "stock", "is_active"]


class RedemptionSerializer(serializers.ModelSerializer):
    reward = RewardSerializer(read_only=True)

    class Meta:
        model = Redemption
        fields = ["id", "reward", "price", "status", "created_at"]
