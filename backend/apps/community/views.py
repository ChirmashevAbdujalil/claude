from django.db.models import Count, Exists, OuterRef
from django.shortcuts import get_object_or_404
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import IsAuthorOrReadOnly, ReadOnlyOrReviewer

from . import services
from .models import Comment, Event, EventRegistration, Post
from .serializers import (
    CheckInSerializer,
    CommentSerializer,
    EventRegistrationSerializer,
    EventSerializer,
    PostSerializer,
)


class PostViewSet(viewsets.ModelViewSet):
    queryset = Post.objects.none()
    """Lenta: talabalar yutuq va loyihalari bilan o'rtoqlashadi."""

    serializer_class = PostSerializer
    permission_classes = [IsAuthorOrReadOnly]
    filterset_fields = ["author", "project"]

    def get_queryset(self):
        liked = Post.likes.through.objects.filter(post_id=OuterRef("pk"), user_id=self.request.user.id)
        return (
            Post.objects.filter(is_hidden=False)
            .select_related("author", "author__faculty")
            .annotate(
                like_count=Count("likes", distinct=True),
                comment_count=Count("comments", distinct=True),
                liked=Exists(liked),
            )
            .order_by("-created_at")
        )

    def perform_create(self, serializer):
        serializer.save(author=self.request.user)

    @extend_schema(request=None, responses={200: dict})
    @action(detail=True, methods=["post"], permission_classes=[IsAuthenticated])
    def like(self, request, pk=None):
        post = self.get_object()
        if post.likes.filter(pk=request.user.pk).exists():
            post.likes.remove(request.user)
            liked = False
        else:
            post.likes.add(request.user)
            liked = True
        return Response({"liked": liked, "like_count": post.likes.count()})

    @extend_schema(request=CommentSerializer, responses=CommentSerializer(many=True))
    @action(detail=True, methods=["get", "post"], permission_classes=[IsAuthenticated])
    def comments(self, request, pk=None):
        post = self.get_object()
        if request.method == "POST":
            serializer = CommentSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            comment = serializer.save(post=post, author=request.user)
            return Response(CommentSerializer(comment).data, status=status.HTTP_201_CREATED)
        return Response(CommentSerializer(post.comments.select_related("author", "author__faculty"), many=True).data)


class CommentDeleteView(APIView):
    @extend_schema(responses={204: None})
    def delete(self, request, pk):
        comment = get_object_or_404(Comment, pk=pk)
        if comment.author_id != request.user.id and not request.user.is_management:
            return Response({"detail": "Ruxsat yo'q"}, status=status.HTTP_403_FORBIDDEN)
        comment.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class EventViewSet(viewsets.ModelViewSet):
    queryset = Event.objects.none()
    serializer_class = EventSerializer
    permission_classes = [ReadOnlyOrReviewer]

    def get_queryset(self):
        mine = EventRegistration.objects.filter(event_id=OuterRef("pk"), user_id=self.request.user.id)
        qs = Event.objects.annotate(
            registered_count=Count("registrations", distinct=True), is_registered=Exists(mine)
        ).order_by("starts_at")
        if self.request.query_params.get("upcoming") == "1":
            qs = qs.filter(ends_at__gte=timezone.now())
        return qs

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    @extend_schema(request=None, responses=EventRegistrationSerializer)
    @action(detail=True, methods=["post"], permission_classes=[IsAuthenticated])
    def register(self, request, pk=None):
        try:
            registration = services.register(self.get_object(), request.user)
        except services.EventError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(EventRegistrationSerializer(registration).data, status=status.HTTP_201_CREATED)

    @extend_schema(responses={200: dict})
    @action(detail=True)
    def qr(self, request, pk=None):
        """Tashkilotchi uchun check-in kodi: frontend uni QR rasmga aylantiradi."""
        event = self.get_object()
        if not (request.user.is_reviewer or event.created_by_id == request.user.id):
            return Response({"detail": "Ruxsat yo'q"}, status=status.HTTP_403_FORBIDDEN)
        return Response({"code": event.checkin_code, "deep_link": f"checkin:{event.checkin_code}"})

    @extend_schema(request=CheckInSerializer, responses=EventRegistrationSerializer)
    @action(detail=False, methods=["post"], url_path="check-in", permission_classes=[IsAuthenticated])
    def check_in(self, request):
        serializer = CheckInSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            registration = services.check_in(serializer.validated_data["code"], request.user)
        except services.EventError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(EventRegistrationSerializer(registration).data)
