from django.urls import path
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register("ai/conversations", views.ConversationViewSet, basename="ai-conversation")

urlpatterns = [
    path("ai/quota/", views.AiQuotaView.as_view(), name="ai-quota"),
    *router.urls,
]
