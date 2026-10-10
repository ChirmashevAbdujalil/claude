from datetime import timedelta

from django.contrib.auth import get_user_model
from django.db.models import Count, IntegerField, Q, Sum, Value
from django.db.models.functions import Coalesce
from django.utils import timezone
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import generics
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import Faculty
from apps.accounts.serializers import LevelSerializer

from .levels import level_for_xp
from .models import Badge, PointTransaction, Streak
from .serializers import (
    BadgeSerializer,
    LeaderboardEntrySerializer,
    LeagueEntrySerializer,
    PointTransactionSerializer,
    StreakSerializer,
    UserBadgeSerializer,
)
from .services import semester_start

LEADERBOARD_SIZE = 50
PERIODS = {"week": 7, "month": 30}


class ArenaSummaryView(APIView):
    """Talabaning o'yin holati: XP, tangalar, daraja, streak, nishonlar."""

    @extend_schema(responses={200: dict})
    def get(self, request):
        user = request.user
        streak = Streak.objects.filter(user=user).first()
        badges = user.badges.select_related("badge")
        return Response(
            {
                "xp": user.xp,
                "coins": user.coins,
                "level": LevelSerializer(level_for_xp(user.xp)).data,
                "streak": StreakSerializer(streak).data
                if streak
                else {"current": 0, "longest": 0, "last_active": None},
                "badges": UserBadgeSerializer(badges, many=True).data,
            }
        )


class BadgeListView(generics.ListAPIView):
    queryset = Badge.objects.all()
    serializer_class = BadgeSerializer
    pagination_class = None

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["earned_codes"] = set(self.request.user.badges.values_list("badge__code", flat=True))
        return context


class TransactionListView(generics.ListAPIView):
    queryset = PointTransaction.objects.none()
    serializer_class = PointTransactionSerializer

    def get_queryset(self):
        return PointTransaction.objects.filter(user=self.request.user)


class LeaderboardView(APIView):
    @extend_schema(
        parameters=[
            OpenApiParameter("period", str, enum=["all", "week", "month"]),
            OpenApiParameter("faculty", int),
            OpenApiParameter("course", int),
        ],
        responses=LeaderboardEntrySerializer(many=True),
    )
    def get(self, request):
        User = get_user_model()
        users = User.objects.filter(role=User.Role.STUDENT, is_active=True, is_public=True)
        faculty = request.query_params.get("faculty")
        course = request.query_params.get("course")
        if faculty and faculty.isdigit():
            users = users.filter(faculty_id=int(faculty))
        if course and course.isdigit():
            users = users.filter(course=int(course))

        period = request.query_params.get("period", "all")
        if period in PERIODS:
            since = timezone.now() - timedelta(days=PERIODS[period])
            users = users.annotate(
                score=Coalesce(
                    Sum("transactions__xp", filter=Q(transactions__created_at__gte=since)),
                    Value(0),
                    output_field=IntegerField(),
                )
            ).filter(score__gt=0)
        else:
            users = users.annotate(score=Coalesce("xp", Value(0)))

        top = users.select_related("faculty").order_by("-score", "id")[:LEADERBOARD_SIZE]
        entries = [
            {
                "rank": index,
                "user_id": user.id,
                "full_name": user.get_full_name() or user.username,
                "faculty": user.faculty.short_name if user.faculty else None,
                "course": user.course,
                "xp": user.score,
            }
            for index, user in enumerate(top, start=1)
        ]

        my_entry = next((e for e in entries if e["user_id"] == request.user.id), None)
        if my_entry is None:
            mine = users.filter(pk=request.user.pk).first()
            if mine is not None:
                my_rank = users.filter(Q(score__gt=mine.score) | Q(score=mine.score, id__lt=mine.id)).count() + 1
                my_entry = {"rank": my_rank, "xp": mine.score}

        return Response({"period": period, "results": entries, "me": my_entry})


class FacultyLeagueView(APIView):
    """Fakultetlar ligasi: joriy semestrda to'plangan XP."""

    @extend_schema(responses=LeagueEntrySerializer(many=True))
    def get(self, request):
        since = semester_start()
        faculties = Faculty.objects.annotate(
            score=Coalesce(
                Sum("users__transactions__xp", filter=Q(users__transactions__created_at__date__gte=since)),
                Value(0),
                output_field=IntegerField(),
            ),
            members=Count("users", filter=Q(users__role="student"), distinct=True),
        ).order_by("-score", "name")
        results = [
            {"rank": i, "faculty_id": f.id, "faculty": f.name, "xp": f.score, "members": f.members}
            for i, f in enumerate(faculties, start=1)
        ]
        return Response({"semester_start": since, "results": results})
