from django.urls import path

from .views import (
    ai,
    arena,
    challenges,
    coins,
    community,
    home,
    onboarding,
    opportunities,
    profile,
    projects,
    public,
    staff,
)

app_name = "web"

urlpatterns = [
    path("", public.landing, name="landing"),
    path("login/", public.login_view, name="login"),
    path("logout/", public.logout_view, name="logout"),
    path("auth/telegram/", public.telegram_login, name="telegram-login"),
    path("u/<slug:slug>/", public.portfolio, name="portfolio"),
    path("menu/", public.menu, name="menu"),
    path("register/", onboarding.register, name="register"),
    path("welcome/", onboarding.welcome, name="welcome"),
    path("welcome/skip/", onboarding.welcome_skip, name="welcome-skip"),
    path("how-it-works/", onboarding.how_it_works, name="how-it-works"),
    path("notifications/", onboarding.notifications, name="notifications"),
    path("notifications/<int:pk>/go/", onboarding.notification_go, name="notification-go"),
    path("app/", home.dashboard, name="dashboard"),
    # Challenge'lar
    path("challenges/", challenges.challenge_list, name="challenges"),
    path("challenges/new/", challenges.challenge_create, name="challenge-create"),
    path("challenges/<int:pk>/", challenges.challenge_detail, name="challenge-detail"),
    path("challenges/<int:pk>/edit/", challenges.challenge_create, name="challenge-edit"),
    # Arena
    path("arena/", arena.arena, name="arena"),
    # Profil
    path("profile/", profile.my_profile, name="profile"),
    path("profile/edit/", profile.edit_profile, name="profile-edit"),
    path("profile/skills/add/", profile.add_skill, name="profile-skill-add"),
    path("profile/skills/<int:pk>/remove/", profile.remove_skill, name="profile-skill-remove"),
    path("profile/achievements/new/", profile.add_achievement, name="profile-achievement-add"),
    path("profile/achievements/<int:pk>/delete/", profile.delete_achievement, name="profile-achievement-delete"),
    # Loyihalar
    path("projects/", projects.project_list, name="projects"),
    path("projects/new/", projects.project_form, name="project-create"),
    path("projects/<int:pk>/", projects.project_detail, name="project-detail"),
    path("projects/<int:pk>/edit/", projects.project_form, name="project-edit"),
    path("projects/<int:pk>/join/", projects.project_join, name="project-join"),
    path("projects/<int:pk>/approve/<int:member_id>/", projects.project_approve, name="project-approve"),
    path("projects/<int:pk>/advance/", projects.project_advance, name="project-advance"),
    # Imkoniyatlar va do'kon
    path("opportunities/", opportunities.opportunity_list, name="opportunities"),
    path("opportunities/new/", opportunities.opportunity_form, name="opportunity-create"),
    path("opportunities/<int:pk>/", opportunities.opportunity_detail, name="opportunity-detail"),
    path("coins/", coins.coins, name="coins"),
    path("shop/", opportunities.shop, name="shop"),
    path("shop/<int:pk>/redeem/", opportunities.redeem, name="shop-redeem"),
    # Hamjamiyat
    path("feed/", community.feed, name="feed"),
    path("feed/<int:pk>/", community.post_detail, name="post-detail"),
    path("feed/<int:pk>/like/", community.post_like, name="post-like"),
    path("feed/<int:pk>/delete/", community.post_delete, name="post-delete"),
    path("events/", community.event_list, name="events"),
    path("events/new/", community.event_form, name="event-create"),
    path("events/check-in/", community.event_checkin, name="event-checkin"),
    path("events/<int:pk>/", community.event_detail, name="event-detail"),
    path("events/<int:pk>/edit/", community.event_form, name="event-edit"),
    path("events/<int:pk>/register/", community.event_register, name="event-register"),
    # AI
    path("ai/", ai.ai_home, name="ai"),
    path("ai/start/", ai.ai_start, name="ai-start"),
    path("ai/<int:pk>/", ai.ai_chat, name="ai-chat"),
    path("ai/<int:pk>/delete/", ai.ai_delete, name="ai-delete"),
    # O'qituvchi va rahbariyat
    path("review/", staff.review_queue, name="review"),
    path("review/submissions/<int:pk>/", staff.review_submission, name="review-submission"),
    path("review/submissions/<int:pk>/ai/", staff.review_submission_ai, name="review-submission-ai"),
    path("review/achievements/<int:pk>/", staff.review_achievement, name="review-achievement"),
    path("review/skills/<int:pk>/endorse/", staff.endorse_skill, name="endorse-skill"),
    path("review/students/<int:user_id>/flag/", staff.talent_flag, name="talent-flag"),
    path("insights/", staff.insights, name="insights"),
]
