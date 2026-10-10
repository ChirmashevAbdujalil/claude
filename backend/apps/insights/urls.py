from django.urls import path

from . import views

urlpatterns = [
    path("insights/dashboard/", views.DashboardView.as_view(), name="insights-dashboard"),
]
