from django.conf import settings
from django.contrib.auth import SESSION_KEY, get_user_model
from django.shortcuts import redirect, render

from .context import activate, default_institution
from .models import Institution

PLATFORM_PATHS = (
    "/billing/",
    "/saas/",
    "/platform/",
    "/admin/",
    "/static/",
    "/media/",
    "/login/",
    "/logout/",
    "/api/docs",
    "/api/schema",
)
# Obunasi to'xtagan OTM ham kirib, to'lov qila olishi kerak
ALWAYS_OPEN = ("/static/", "/media/", "/admin/", "/billing/", "/settings/otm/", "/login/", "/logout/")


class UnknownInstitution(Exception):
    pass


def resolve(host: str):
    """Manzil bo'yicha OTMni topadi. Platformaning o'z domeni uchun None qaytaradi."""
    host = host.split(":")[0].lower().rstrip(".")
    by_domain = Institution.objects.filter(domain__iexact=host).first()
    if by_domain:
        return by_domain
    base = settings.SAAS_BASE_DOMAIN.lower()
    for suffix in filter(None, (base, "localhost")):
        if host.endswith("." + suffix):
            sub = host[: -(len(suffix) + 1)]
            if sub == "www":
                return None if base and suffix == base else default_institution()
            found = Institution.objects.filter(slug=sub).first()
            if found is None:
                raise UnknownInstitution(sub)
            return found
    if base and host == base:
        return None
    return default_institution()


def _is_superuser_session(request) -> bool:
    user_id = request.session.get(SESSION_KEY)
    if not user_id:
        return False
    # Menejer joriy OTM bo'yicha cheklaydi; bu yerda kontekst hali o'rnatilmagan, shuning uchun hamma ko'rinadi
    return get_user_model().objects.filter(pk=user_id, is_superuser=True).exists()


class TenantMiddleware:
    """So'rov qaysi OTMniki ekanini aniqlaydi va butun so'rov davomida shu OTM kontekstini o'rnatadi."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        path = request.path
        try:
            institution = resolve(request.get_host())
        except UnknownInstitution:
            request.institution = None
            return render(request, "web/tenant_not_found.html", status=404)

        is_platform_host = institution is None
        if path.startswith("/admin/") and _is_superuser_session(request):
            institution = None  # platforma egasi admin panelda hamma OTMni ko'radi
        request.institution = institution
        request.is_platform_host = is_platform_host

        if is_platform_host and not path.startswith(PLATFORM_PATHS):
            return redirect("/saas/")
        if institution is not None and not institution.is_active and not path.startswith(ALWAYS_OPEN):
            return render(request, "web/tenant_inactive.html", {"inst": institution}, status=503)

        with activate(institution):
            return self.get_response(request)
