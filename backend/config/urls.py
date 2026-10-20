from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path, re_path
from django.views.static import serve
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

from apps.notifications.views import telegram_webhook

admin.site.site_header = "Talent Hub boshqaruvi"
admin.site.site_title = "Talent Hub"
admin.site.index_title = "Boshqaruv paneli"

api_patterns = [
    path("", include("apps.accounts.urls")),
    path("", include("apps.profiles.urls")),
    path("", include("apps.arena.urls")),
    path("", include("apps.discovery.urls")),
    path("", include("apps.projects.urls")),
    path("", include("apps.opportunities.urls")),
    path("", include("apps.community.urls")),
    path("", include("apps.insights.urls")),
    path("", include("apps.ai.urls")),
    path("", include("apps.notifications.urls")),
]

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/v1/", include(api_patterns)),
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="docs"),
    path("telegram/webhook/", telegram_webhook, name="telegram-webhook"),
    path("billing/", include("apps.billing.urls")),
    path("", include("apps.web.urls")),
]

handler404 = "apps.web.views.public.page_not_found"

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
else:
    # OTM logotipi va mas'ul shaxs rasmi ommaviy: alohida veb-server bo'lmasa ham ko'rinadi
    urlpatterns += [
        re_path(r"^media/(?P<path>institutions/[\w./-]+)$", serve, {"document_root": settings.MEDIA_ROOT}),
    ]
