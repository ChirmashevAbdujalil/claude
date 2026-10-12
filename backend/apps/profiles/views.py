from django.contrib.auth import get_user_model
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import IsReviewer, ReadOnlyOrReviewer
from apps.accounts.serializers import LevelSerializer
from apps.arena.levels import level_for_xp
from apps.arena.serializers import UserBadgeSerializer

from . import services
from .models import Achievement, Skill, UserSkill
from .serializers import (
    AchievementReviewSerializer,
    AchievementSerializer,
    EndorseSerializer,
    SkillSerializer,
    UserSkillSerializer,
)


class SkillViewSet(viewsets.ModelViewSet):
    queryset = Skill.objects.all()
    serializer_class = SkillSerializer
    permission_classes = [ReadOnlyOrReviewer]
    pagination_class = None
    filterset_fields = ["category"]
    search_fields = ["name"]


class MySkillViewSet(viewsets.ModelViewSet):
    queryset = UserSkill.objects.none()
    serializer_class = UserSkillSerializer
    pagination_class = None

    def get_queryset(self):
        return UserSkill.objects.filter(user=self.request.user).select_related("skill")

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    @extend_schema(responses={200: dict})
    @action(detail=False, url_path="map")
    def skill_map(self, request):
        return Response(services.skill_map(request.user))


class UserSkillEndorseViewSet(viewsets.GenericViewSet):
    queryset = UserSkill.objects.select_related("user", "skill")
    permission_classes = [IsReviewer]

    @extend_schema(request=EndorseSerializer, responses={201: dict})
    @action(detail=True, methods=["post"])
    def endorse(self, request, pk=None):
        serializer = EndorseSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            services.endorse(self.get_object(), request.user, serializer.validated_data.get("comment", ""))
        except services.ReviewError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response({"detail": "Ko'nikma tasdiqlandi"}, status=status.HTTP_201_CREATED)


class AchievementViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    """Talaba o'z yutuqlarini ko'radi; o'qituvchilar barchasini ko'rib, tasdiqlaydi."""

    queryset = Achievement.objects.none()
    serializer_class = AchievementSerializer
    filterset_fields = ["status", "kind"]

    def get_queryset(self):
        qs = Achievement.objects.select_related("user", "user__faculty")
        if self.request.user.is_reviewer and self.request.query_params.get("scope") == "all":
            return qs
        return qs.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    def destroy(self, request, *args, **kwargs):
        achievement = self.get_object()
        if achievement.status != Achievement.Status.PENDING or achievement.user_id != request.user.id:
            return Response(
                {"detail": "Faqat kutilayotgan o'z yutug'ingizni o'chira olasiz"}, status=status.HTTP_400_BAD_REQUEST
            )
        return super().destroy(request, *args, **kwargs)

    @extend_schema(request=AchievementReviewSerializer, responses=AchievementSerializer)
    @action(detail=True, methods=["post"], permission_classes=[IsReviewer])
    def review(self, request, pk=None):
        achievement = get_object_or_404(Achievement, pk=pk)
        serializer = AchievementReviewSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        try:
            achievement = services.review_achievement(
                achievement, request.user, data["approve"], data.get("xp"), data.get("comment", "")
            )
        except services.ReviewError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(AchievementSerializer(achievement, context={"request": request}).data)


class PortfolioView(APIView):
    """Ommaviy portfolio sahifasi: talent.andti.uz/u/<slug>"""

    permission_classes = [AllowAny]

    @extend_schema(responses={200: dict})
    def get(self, request, slug):
        User = get_user_model()
        user = get_object_or_404(
            User.objects.select_related("faculty"), portfolio_slug=slug, is_public=True, is_active=True
        )
        skills = UserSkill.objects.filter(user=user).select_related("skill")
        achievements = Achievement.objects.filter(user=user, status=Achievement.Status.APPROVED)
        projects = user.project_memberships.filter(status="active").select_related("project")
        return Response(
            {
                "full_name": user.get_full_name() or user.username,
                "faculty": user.faculty.name if user.faculty else None,
                "course": user.course,
                "bio": user.bio,
                "github_url": user.github_url,
                "linkedin_url": user.linkedin_url,
                "xp": user.xp,
                "level": LevelSerializer(level_for_xp(user.xp)).data,
                "skill_map": services.skill_map(user),
                "skills": UserSkillSerializer(skills, many=True, context={"request": request}).data,
                "achievements": [
                    {"kind": a.get_kind_display(), "title": a.title, "achieved_on": a.achieved_on} for a in achievements
                ],
                "badges": UserBadgeSerializer(user.badges.select_related("badge"), many=True).data,
                "projects": [
                    {
                        "id": m.project_id,
                        "title": m.project.title,
                        "stage": m.project.get_stage_display(),
                        "role": m.role,
                    }
                    for m in projects
                ],
            }
        )
