from django.urls import path
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register("posts", views.PostViewSet, basename="post")
router.register("events", views.EventViewSet, basename="event")

urlpatterns = [
    path("comments/<int:pk>/", views.CommentDeleteView.as_view(), name="comment-delete"),
    *router.urls,
]
