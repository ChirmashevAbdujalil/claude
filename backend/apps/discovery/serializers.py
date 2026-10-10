from rest_framework import serializers

from apps.accounts.serializers import UserBriefSerializer

from .models import Challenge, Submission, TalentFlag


class ChallengeSerializer(serializers.ModelSerializer):
    is_open = serializers.BooleanField(read_only=True)
    auto_checked = serializers.SerializerMethodField()
    my_submission = serializers.SerializerMethodField()
    xp_reward = serializers.IntegerField(required=False, min_value=0, max_value=1000)

    class Meta:
        model = Challenge
        fields = [
            "id",
            "title",
            "description",
            "kind",
            "difficulty",
            "category",
            "xp_reward",
            "expected_answer",
            "auto_checked",
            "faculty",
            "starts_at",
            "ends_at",
            "is_published",
            "is_open",
            "my_submission",
        ]
        extra_kwargs = {"expected_answer": {"write_only": True}}

    def get_auto_checked(self, obj) -> bool:
        return bool(obj.expected_answer)

    def get_my_submission(self, obj) -> dict | None:
        submissions = self.context.get("my_submissions", {})
        submission = submissions.get(obj.pk)
        if submission is None:
            return None
        return {"id": submission.pk, "status": submission.status, "xp_awarded": submission.xp_awarded}

    def validate(self, attrs):
        starts_at = attrs.get("starts_at", getattr(self.instance, "starts_at", None))
        ends_at = attrs.get("ends_at", getattr(self.instance, "ends_at", None))
        if starts_at and ends_at and ends_at <= starts_at:
            raise serializers.ValidationError("Tugash vaqti boshlanishdan keyin bo'lishi kerak")
        return attrs


class SubmitSerializer(serializers.Serializer):
    answer = serializers.CharField(required=False, allow_blank=True, default="")
    link = serializers.URLField(required=False, allow_blank=True, default="")


class SubmissionSerializer(serializers.ModelSerializer):
    user = UserBriefSerializer(read_only=True)
    challenge_title = serializers.CharField(source="challenge.title", read_only=True)

    class Meta:
        model = Submission
        fields = [
            "id",
            "challenge",
            "challenge_title",
            "user",
            "answer",
            "link",
            "status",
            "score",
            "feedback",
            "xp_awarded",
            "created_at",
        ]
        read_only_fields = fields


class ReviewSerializer(serializers.Serializer):
    accept = serializers.BooleanField()
    score = serializers.IntegerField(required=False, allow_null=True, min_value=0, max_value=100)
    feedback = serializers.CharField(required=False, allow_blank=True, default="")


class TalentFlagSerializer(serializers.ModelSerializer):
    student_detail = UserBriefSerializer(source="student", read_only=True)
    flagged_by = UserBriefSerializer(read_only=True)

    class Meta:
        model = TalentFlag
        fields = ["id", "student", "student_detail", "flagged_by", "area", "note", "created_at"]

    def validate_student(self, value):
        if value.role != value.Role.STUDENT:
            raise serializers.ValidationError("Faqat talabani belgilash mumkin")
        return value
