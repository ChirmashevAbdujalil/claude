from rest_framework import serializers

from apps.accounts.serializers import UserBriefSerializer
from apps.profiles.models import Skill
from apps.profiles.serializers import SkillSerializer

from .models import Project, ProjectMember


class ProjectMemberSerializer(serializers.ModelSerializer):
    user = UserBriefSerializer(read_only=True)

    class Meta:
        model = ProjectMember
        fields = ["id", "user", "role", "message", "status", "joined_at"]


class ProjectSerializer(serializers.ModelSerializer):
    owner = UserBriefSerializer(read_only=True)
    skills_needed = SkillSerializer(many=True, read_only=True)
    skill_ids = serializers.PrimaryKeyRelatedField(
        source="skills_needed", queryset=Skill.objects.all(), many=True, write_only=True, required=False
    )
    members = serializers.SerializerMethodField()
    stage_display = serializers.CharField(source="get_stage_display", read_only=True)

    class Meta:
        model = Project
        fields = [
            "id",
            "title",
            "description",
            "problem",
            "stage",
            "stage_display",
            "owner",
            "skills_needed",
            "skill_ids",
            "repo_url",
            "demo_url",
            "is_recruiting",
            "members",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["stage"]

    def get_members(self, obj) -> list[dict]:
        request = self.context.get("request")
        members = obj.members.all()
        # Kutilayotgan so'rovlarni faqat asoschi ko'radi
        if not (request and request.user.id == obj.owner_id):
            members = [m for m in members if m.status == ProjectMember.Status.ACTIVE]
        return ProjectMemberSerializer(members, many=True).data


class JoinSerializer(serializers.Serializer):
    role = serializers.CharField(max_length=100, required=False, default="A'zo")
    message = serializers.CharField(max_length=500, required=False, allow_blank=True, default="")


class ApproveSerializer(serializers.Serializer):
    member_id = serializers.IntegerField()


class TeammateSerializer(UserBriefSerializer):
    matched = serializers.IntegerField()
    endorsed = serializers.IntegerField()

    class Meta(UserBriefSerializer.Meta):
        fields = UserBriefSerializer.Meta.fields + ["matched", "endorsed"]
