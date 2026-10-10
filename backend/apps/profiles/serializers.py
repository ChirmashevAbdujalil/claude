from rest_framework import serializers

from apps.accounts.serializers import UserBriefSerializer

from .models import Achievement, Skill, UserSkill


class SkillSerializer(serializers.ModelSerializer):
    class Meta:
        model = Skill
        fields = ["id", "name", "category"]


class UserSkillSerializer(serializers.ModelSerializer):
    skill = SkillSerializer(read_only=True)
    skill_id = serializers.PrimaryKeyRelatedField(source="skill", queryset=Skill.objects.all(), write_only=True)
    endorsement_count = serializers.IntegerField(source="endorsements.count", read_only=True)

    class Meta:
        model = UserSkill
        fields = ["id", "skill", "skill_id", "level", "endorsement_count"]

    def validate(self, attrs):
        user = self.context["request"].user
        skill = attrs.get("skill")
        if skill and self.instance is None and UserSkill.objects.filter(user=user, skill=skill).exists():
            raise serializers.ValidationError("Bu ko'nikma profilingizda allaqachon bor")
        return attrs


class EndorseSerializer(serializers.Serializer):
    comment = serializers.CharField(max_length=255, required=False, allow_blank=True)


class AchievementSerializer(serializers.ModelSerializer):
    user = UserBriefSerializer(read_only=True)

    class Meta:
        model = Achievement
        fields = [
            "id",
            "user",
            "kind",
            "title",
            "description",
            "proof",
            "proof_url",
            "achieved_on",
            "status",
            "review_comment",
            "xp_awarded",
            "created_at",
        ]
        read_only_fields = ["status", "review_comment", "xp_awarded", "created_at"]

    def validate(self, attrs):
        if self.instance is None and not attrs.get("proof") and not attrs.get("proof_url"):
            raise serializers.ValidationError("Tasdiqlovchi hujjat yoki havola kerak")
        return attrs


class AchievementReviewSerializer(serializers.Serializer):
    approve = serializers.BooleanField()
    xp = serializers.IntegerField(required=False, min_value=0, max_value=Achievement.MAX_XP)
    comment = serializers.CharField(max_length=255, required=False, allow_blank=True)
