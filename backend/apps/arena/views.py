from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import generics
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.serializers import LevelSerializer

from . import selectors
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
        params = request.query_params
        board = selectors.leaderboard(
            request.user, params.get("period", "all"), params.get("faculty"), params.get("course")
        )
        entries = [
            {
                "rank": row.rank,
                "user_id": row.user.id,
                "full_name": row.user.get_full_name() or row.user.username,
                "faculty": row.user.faculty.short_name if row.user.faculty else None,
                "course": row.user.course,
                "xp": row.score,
            }
            for row in board.rows
        ]
        me = {"rank": board.me.rank, "xp": board.me.score} if board.me else None
        return Response({"period": board.period, "results": entries, "me": me})


class FacultyLeagueView(APIView):
    """Fakultetlar ligasi: joriy semestrda to'plangan XP."""

    @extend_schema(responses=LeagueEntrySerializer(many=True))
    def get(self, request):
        since, results = selectors.faculty_league()
        return Response({"semester_start": since, "results": results})
