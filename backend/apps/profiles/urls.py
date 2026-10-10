from django.urls import path
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register("skills", views.SkillViewSet, basename="skill")
router.register("me/skills", views.MySkillViewSet, basename="my-skill")
router.register("user-skills", views.UserSkillEndorseViewSet, basename="user-skill")
router.register("achievements", views.AchievementViewSet, basename="achievement")

urlpatterns = [
    path("portfolio/<slug:slug>/", views.PortfolioView.as_view(), name="portfolio"),
    *router.urls,
]
