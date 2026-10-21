"""cPanel «Setup Python App» (Phusion Passenger / LiteSpeed) uchun kirish nuqtasi.

Application startup file = passenger_wsgi.py, Entry point = application.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

from config.wsgi import application as django_application  # noqa: E402


def application(environ, start_response):
    # Hosting veb-serveri HTTPS'ni turlicha bildiradi: Django so'rov https orqali kelganini aniq bilsin
    # (aks holda http -> https yo'naltirish cheksiz takrorlanadi va xavfsiz cookie'lar ishlamaydi)
    if (
        environ.get("HTTPS", "").lower() in ("on", "1")
        or environ.get("HTTP_X_FORWARDED_PROTO", "").lower() == "https"
        or environ.get("REQUEST_SCHEME", "").lower() == "https"
        or environ.get("SERVER_PORT") == "443"
    ):
        environ["wsgi.url_scheme"] = "https"
    return django_application(environ, start_response)
