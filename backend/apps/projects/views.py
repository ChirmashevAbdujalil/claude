from django.db.models import Prefetch
from drf_spectacular.utils import extend_schema
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.accounts.permissions import IsAuthorOrReadOnly

from . import services
from .models import Project, ProjectMember
from .serializers import (
    ApproveSerializer,
    JoinSerializer,
    ProjectMemberSerializer,
    ProjectSerializer,
    TeammateSerializer,
)


class ProjectViewSet(viewsets.ModelViewSet):
    queryset = Project.objects.none()
    serializer_class = ProjectSerializer
    permission_classes = [IsAuthorOrReadOnly]
    author_field = "owner"
    filterset_fields = ["stage", "is_recruiting", "skills_needed"]
    search_fields = ["title", "description", "problem"]

    def get_queryset(self):
        qs = Project.objects.select_related("owner", "owner__faculty").prefetch_related(
            "skills_needed",
            Prefetch("members", queryset=ProjectMember.objects.select_related("user", "user__faculty")),
        )
        if self.request.query_params.get("mine") == "1":
            qs = qs.filter(members__user=self.request.user).distinct()
        return qs

    def perform_create(self, serializer):
        serializer.instance = services.create_project(self.request.user, **serializer.validated_data)

    def _run(self, func, *args, serializer_class=ProjectSerializer, code=status.HTTP_200_OK):
        try:
            result = func(*args)
        except services.ProjectError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(serializer_class(result, context=self.get_serializer_context()).data, status=code)

    @extend_schema(request=JoinSerializer, responses=ProjectMemberSerializer)
    @action(detail=True, methods=["post"], permission_classes=[IsAuthenticated])
    def join(self, request, pk=None):
        serializer = JoinSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        return self._run(
            services.request_join,
            self.get_object(),
            request.user,
            data["role"],
            data["message"],
            serializer_class=ProjectMemberSerializer,
            code=status.HTTP_201_CREATED,
        )

    @extend_schema(request=ApproveSerializer, responses=ProjectMemberSerializer)
    @action(detail=True, methods=["post"], permission_classes=[IsAuthenticated])
    def approve(self, request, pk=None):
        serializer = ApproveSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return self._run(
            services.approve_member,
            self.get_object(),
            request.user,
            serializer.validated_data["member_id"],
            serializer_class=ProjectMemberSerializer,
        )

    @extend_schema(request=None, responses=ProjectSerializer)
    @action(detail=True, methods=["post"], permission_classes=[IsAuthenticated])
    def advance(self, request, pk=None):
        return self._run(services.advance_stage, self.get_object(), request.user)

    @extend_schema(responses=TeammateSerializer(many=True))
    @action(detail=True)
    def recommendations(self, request, pk=None):
        project = self.get_object()
        return Response(TeammateSerializer(services.recommend_teammates(project), many=True).data)
