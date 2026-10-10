from rest_framework import serializers

from apps.accounts.serializers import UserBriefSerializer

from .models import Comment, Event, EventRegistration, Post


class CommentSerializer(serializers.ModelSerializer):
    author = UserBriefSerializer(read_only=True)

    class Meta:
        model = Comment
        fields = ["id", "author", "text", "created_at"]


class PostSerializer(serializers.ModelSerializer):
    author = UserBriefSerializer(read_only=True)
    like_count = serializers.IntegerField(read_only=True)
    comment_count = serializers.IntegerField(read_only=True)
    liked = serializers.BooleanField(read_only=True)

    class Meta:
        model = Post
        fields = ["id", "author", "text", "image", "project", "like_count", "comment_count", "liked", "created_at"]


class EventSerializer(serializers.ModelSerializer):
    registered_count = serializers.IntegerField(read_only=True)
    is_registered = serializers.BooleanField(read_only=True)

    class Meta:
        model = Event
        fields = [
            "id",
            "title",
            "description",
            "location",
            "starts_at",
            "ends_at",
            "capacity",
            "xp_reward",
            "registered_count",
            "is_registered",
        ]

    def validate(self, attrs):
        starts_at = attrs.get("starts_at", getattr(self.instance, "starts_at", None))
        ends_at = attrs.get("ends_at", getattr(self.instance, "ends_at", None))
        if starts_at and ends_at and ends_at <= starts_at:
            raise serializers.ValidationError("Tugash vaqti boshlanishdan keyin bo'lishi kerak")
        return attrs


class CheckInSerializer(serializers.Serializer):
    code = serializers.CharField(max_length=64)


class EventRegistrationSerializer(serializers.ModelSerializer):
    event_title = serializers.CharField(source="event.title", read_only=True)

    class Meta:
        model = EventRegistration
        fields = ["id", "event", "event_title", "registered_at", "attended_at"]
