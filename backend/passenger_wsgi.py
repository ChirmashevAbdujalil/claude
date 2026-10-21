"""cPanel «Setup Python App» (Phusion Passenger) uchun kirish nuqtasi: Application startup file = passenger_wsgi.py."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

from config.wsgi import application  # noqa: E402,F401
