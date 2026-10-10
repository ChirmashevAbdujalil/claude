from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

admin.site.site_header = "ADTI Talent Hub boshqaruvi"
admin.site.site_title = "ADTI Talent Hub"
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
]

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/v1/", include(api_patterns)),
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="docs"),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
