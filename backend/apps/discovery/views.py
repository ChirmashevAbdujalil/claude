from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.accounts.permissions import IsReviewer, ReadOnlyOrReviewer

from . import services
from .models import Challenge, Submission, TalentFlag
from .serializers import (
    ChallengeSerializer,
    ReviewSerializer,
    SubmissionSerializer,
    SubmitSerializer,
    TalentFlagSerializer,
)


class ChallengeViewSet(viewsets.ModelViewSet):
    queryset = Challenge.objects.none()
    serializer_class = ChallengeSerializer
    permission_classes = [ReadOnlyOrReviewer]
    filterset_fields = ["kind", "difficulty", "category"]
    search_fields = ["title", "description"]

    def get_queryset(self):
        qs = Challenge.objects.all()
        user = self.request.user
        if user.is_reviewer:
            return qs
        now = timezone.now()
        qs = qs.filter(is_published=True, starts_at__lte=now).filter(
            Q(faculty__isnull=True) | Q(faculty_id=user.faculty_id)
        )
        if self.request.query_params.get("state") != "all":
            qs = qs.filter(ends_at__gte=now)
        return qs

    def get_serializer_context(self):
        context = super().get_serializer_context()
        if self.request.user.is_authenticated:
            context["my_submissions"] = {s.challenge_id: s for s in Submission.objects.filter(user=self.request.user)}
        return context

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    @extend_schema(request=SubmitSerializer, responses=SubmissionSerializer)
    @action(detail=True, methods=["post"], permission_classes=[IsAuthenticated])
    def submit(self, request, pk=None):
        challenge = self.get_object()
        serializer = SubmitSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            submission = services.submit(challenge, request.user, **serializer.validated_data)
        except services.SubmissionError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(SubmissionSerializer(submission).data, status=status.HTTP_201_CREATED)


class SubmissionViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    queryset = Submission.objects.none()
    serializer_class = SubmissionSerializer
    filterset_fields = ["status", "challenge"]

    def get_queryset(self):
        qs = Submission.objects.select_related("challenge", "user", "user__faculty")
        if self.request.user.is_reviewer and self.request.query_params.get("scope") == "all":
            return qs
        return qs.filter(user=self.request.user)

    @extend_schema(request=ReviewSerializer, responses=SubmissionSerializer)
    @action(detail=True, methods=["post"], permission_classes=[IsReviewer])
    def review(self, request, pk=None):
        submission = get_object_or_404(Submission, pk=pk)
        serializer = ReviewSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            submission = services.review(submission, request.user, **serializer.validated_data)
        except services.SubmissionError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(SubmissionSerializer(submission).data)


class TalentFlagViewSet(viewsets.ModelViewSet):
    queryset = TalentFlag.objects.none()
    serializer_class = TalentFlagSerializer
    permission_classes = [IsReviewer]
    filterset_fields = ["area", "student", "student__faculty"]

    def get_queryset(self):
        return TalentFlag.objects.select_related("student", "student__faculty", "flagged_by")

    def perform_create(self, serializer):
        serializer.save(flagged_by=self.request.user)
