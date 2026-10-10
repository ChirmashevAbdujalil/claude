from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register("opportunities", views.OpportunityViewSet, basename="opportunity")
router.register("me/applications", views.MyApplicationViewSet, basename="my-application")
router.register("rewards", views.RewardViewSet, basename="reward")
router.register("me/redemptions", views.MyRedemptionViewSet, basename="my-redemption")

urlpatterns = router.urls
