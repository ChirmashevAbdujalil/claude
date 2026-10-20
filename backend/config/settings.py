"""ANDTI Talent Hub sozlamalari.

Barcha maxfiy qiymatlar muhit o'zgaruvchilaridan (.env) olinadi.
"""

import os
from datetime import timedelta
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


def env_bool(name: str, default: bool = False) -> bool:
    return os.environ.get(name, str(default)).lower() in {"1", "true", "yes", "on"}


def env_list(name: str, default: str = "") -> list[str]:
    return [item.strip() for item in os.environ.get(name, default).split(",") if item.strip()]


DEBUG = env_bool("DJANGO_DEBUG", False)
SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "")
if not SECRET_KEY:
    if not DEBUG:
        raise RuntimeError(
            "DJANGO_SECRET_KEY o'rnatilmagan. Lokal ishga tushirish uchun backend papkasida .env faylini yarating: "
            "Windows'da 'copy .env.example .env', Mac/Linux'da 'cp .env.example .env'"
        )
    SECRET_KEY = "dev-only-insecure-key"

ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1,.localhost")
if DEBUG and ".localhost" not in ALLOWED_HOSTS:
    # Lokal SaaS sinovi: <otm>.localhost:8000 subdomenlari doim ochiq
    ALLOWED_HOSTS.append(".localhost")
CSRF_TRUSTED_ORIGINS = env_list("DJANGO_CSRF_TRUSTED_ORIGINS")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "django_filters",
    "drf_spectacular",
    "apps.tenants",
    "apps.billing",
    "apps.accounts",
    "apps.profiles",
    "apps.arena",
    "apps.discovery",
    "apps.projects",
    "apps.opportunities",
    "apps.community",
    "apps.insights",
    "apps.ai",
    "apps.notifications",
    "apps.audit",
    "apps.talent",
    "apps.surveys",
    "apps.web",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "apps.tenants.middleware.TenantMiddleware",
    "django.middleware.common.CommonMiddleware",
    "apps.surveys.middleware.UploadLimitMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "apps.audit.middleware.AuditMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "apps.web.context_processors.navigation",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

if os.environ.get("POSTGRES_DB"):
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": os.environ["POSTGRES_DB"],
            "USER": os.environ.get("POSTGRES_USER", "postgres"),
            "PASSWORD": os.environ.get("POSTGRES_PASSWORD", ""),
            "HOST": os.environ.get("POSTGRES_HOST", "localhost"),
            "PORT": os.environ.get("POSTGRES_PORT", "5432"),
            "CONN_MAX_AGE": 60,
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }

AUTH_USER_MODEL = "accounts.User"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "uz"
TIME_ZONE = "Asia/Tashkent"
USE_I18N = True
USE_TZ = True

LOGIN_URL = "web:login"
LOGIN_REDIRECT_URL = "web:dashboard"

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}
MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"
# So'rovnomaga yuklangan fayllar: MEDIA_URL orqali berilmaydi, faqat ruxsatni tekshiradigan sahifa orqali
PRIVATE_MEDIA_ROOT = Path(os.environ.get("PRIVATE_MEDIA_ROOT") or BASE_DIR / "private_media")

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework_simplejwt.authentication.JWTAuthentication",
        "rest_framework.authentication.SessionAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"],
    "DEFAULT_FILTER_BACKENDS": [
        "django_filters.rest_framework.DjangoFilterBackend",
        "rest_framework.filters.SearchFilter",
        "rest_framework.filters.OrderingFilter",
    ],
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 20,
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_THROTTLE_CLASSES": [
        "rest_framework.throttling.UserRateThrottle",
        "rest_framework.throttling.AnonRateThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": {"user": "120/min", "anon": "30/min"},
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(hours=2),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=30),
    "ROTATE_REFRESH_TOKENS": True,
}

SPECTACULAR_SETTINGS = {
    "TITLE": "ANDTI Talent Hub API",
    "DESCRIPTION": "Iqtidorli talabalarni kashf qilish, rivojlantirish va imkoniyatlarga ulash platformasi",
    "VERSION": "0.1.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "ENUM_NAME_OVERRIDES": {"SkillCategoryEnum": "apps.profiles.models.Skill.Category"},
}

# Telegram Mini App orqali kirish
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_AUTH_MAX_AGE = int(os.environ.get("TELEGRAM_AUTH_MAX_AGE", 86400))
TELEGRAM_WEBHOOK_SECRET = os.environ.get("TELEGRAM_WEBHOOK_SECRET", "")

# Saytning tashqi manzili: Telegram tugmalari va xabarlardagi havolalar uchun
SITE_URL = os.environ.get("SITE_URL", "")

# SaaS: bitta platformada bir nechta OTM. Har bir OTM o'z subdomenida ishlaydi: <slug>.SAAS_BASE_DOMAIN
# Bo'sh bo'lsa, platforma bitta OTM (DEFAULT_INSTITUTION) uchun ishlaydi. Lokal sinov: <slug>.localhost:8000
SAAS_BASE_DOMAIN = os.environ.get("SAAS_BASE_DOMAIN", "")
# Harakatlar jurnali: proksi ortida haqiqiy IP X-Forwarded-For sarlavhasidan olinadi
AUDIT_TRUST_X_FORWARDED_FOR = env_bool("AUDIT_TRUST_X_FORWARDED_FOR", False)
DEFAULT_INSTITUTION_SLUG = os.environ.get("DEFAULT_INSTITUTION_SLUG", "andti")
DEFAULT_INSTITUTION_NAME = os.environ.get("DEFAULT_INSTITUTION_NAME", "Andijon davlat texnika instituti")
DEFAULT_INSTITUTION_SHORT = os.environ.get("DEFAULT_INSTITUTION_SHORT", "ANDTI")

# To'lov tizimlari (OTM obunasi uchun). Kalitlar kassa kabinetidan olinadi; bo'sh bo'lsa tugma ko'rinmaydi.
PAYME_MERCHANT_ID = os.environ.get("PAYME_MERCHANT_ID", "")
PAYME_KEY = os.environ.get("PAYME_KEY", "")
PAYME_TEST = env_bool("PAYME_TEST", True)
PAYME_ACCOUNT_FIELD = os.environ.get("PAYME_ACCOUNT_FIELD", "order_id")
CLICK_SERVICE_ID = os.environ.get("CLICK_SERVICE_ID", "")
CLICK_MERCHANT_ID = os.environ.get("CLICK_MERCHANT_ID", "")
CLICK_SECRET_KEY = os.environ.get("CLICK_SECRET_KEY", "")
CLICK_MERCHANT_USER_ID = os.environ.get("CLICK_MERCHANT_USER_ID", "")
# Homiylar sahifasidagi aloqa: email, @telegram yoki to'liq havola
SPONSOR_CONTACT = os.environ.get("SPONSOR_CONTACT", "@chirmashev")

# Talabalar o'zlari ro'yxatdan o'ta oladimi
REGISTRATION_OPEN = env_bool("REGISTRATION_OPEN", True)

# AI Mentor
ANTHROPIC_MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-opus-5-5")
AI_DAILY_MESSAGE_LIMIT = int(os.environ.get("AI_DAILY_MESSAGE_LIMIT", 30))
RESUME_AI_DAILY_LIMIT = int(os.environ.get("RESUME_AI_DAILY_LIMIT", 5))
AI_HISTORY_MESSAGES = int(os.environ.get("AI_HISTORY_MESSAGES", 20))

# Ball iqtisodiyoti
ARENA_DAILY_XP_CAP = int(os.environ.get("ARENA_DAILY_XP_CAP", 1000))

if not DEBUG:
    # Production'da statik fayllarni gunicorn orqali whitenoise beradi
    MIDDLEWARE.insert(1, "whitenoise.middleware.WhiteNoiseMiddleware")
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
