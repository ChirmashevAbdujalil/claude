from rest_framework import serializers

from apps.arena.levels import level_for_xp

from .models import Faculty, User


class FacultySerializer(serializers.ModelSerializer):
    class Meta:
        model = Faculty
        fields = ["id", "name", "short_name"]


class LevelSerializer(serializers.Serializer):
    number = serializers.IntegerField()
    name = serializers.CharField()
    min_xp = serializers.IntegerField()
    next_level_xp = serializers.IntegerField(allow_null=True)
    progress = serializers.FloatField()


class UserBriefSerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()
    faculty = serializers.SlugRelatedField(slug_field="short_name", read_only=True)

    class Meta:
        model = User
        fields = ["id", "username", "full_name", "avatar", "faculty", "course", "xp"]

    def get_full_name(self, obj) -> str:
        return obj.get_full_name() or obj.username


class MeSerializer(serializers.ModelSerializer):
    faculty_id = serializers.PrimaryKeyRelatedField(
        source="faculty", queryset=Faculty.objects.all(), allow_null=True, required=False
    )
    faculty = FacultySerializer(read_only=True)
    level = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "first_name",
            "last_name",
            "role",
            "faculty",
            "faculty_id",
            "course",
            "bio",
            "avatar",
            "github_url",
            "linkedin_url",
            "portfolio_slug",
            "is_public",
            "xp",
            "coins",
            "level",
        ]
        read_only_fields = ["id", "username", "role", "xp", "coins"]

    def get_level(self, obj) -> dict:
        return LevelSerializer(level_for_xp(obj.xp)).data

    def validate_course(self, value):
        if value is not None and not 1 <= value <= 6:
            raise serializers.ValidationError("Kurs 1 dan 6 gacha bo'lishi kerak")
        return value


class TelegramAuthSerializer(serializers.Serializer):
    init_data = serializers.CharField()


class TokenPairSerializer(serializers.Serializer):
    access = serializers.CharField()
    refresh = serializers.CharField()
    created = serializers.BooleanField()
