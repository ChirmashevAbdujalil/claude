from django.urls import path

from . import views

urlpatterns = [
    path("arena/me/", views.ArenaSummaryView.as_view(), name="arena-me"),
    path("arena/badges/", views.BadgeListView.as_view(), name="arena-badges"),
    path("arena/transactions/", views.TransactionListView.as_view(), name="arena-transactions"),
    path("arena/leaderboard/", views.LeaderboardView.as_view(), name="arena-leaderboard"),
    path("arena/league/", views.FacultyLeagueView.as_view(), name="arena-league"),
]
