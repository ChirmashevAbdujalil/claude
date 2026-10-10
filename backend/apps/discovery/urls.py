from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register("challenges", views.ChallengeViewSet, basename="challenge")
router.register("submissions", views.SubmissionViewSet, basename="submission")
router.register("talent-flags", views.TalentFlagViewSet, basename="talent-flag")

urlpatterns = router.urls
