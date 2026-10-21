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


# Asosiy domen: .env bo'lmasa ham sayt shu domenda ishlaydi (ahost.uz, cPanel)
SITE_DOMAIN = os.environ.get("SITE_DOMAIN", "iqtidorasti.uz")


def secret_key_file(path: Path) -> str:
    """Maxfiy kalit .env da berilmagan bo'lsa: birinchi ishga tushishda yaratiladi va faqat serverda saqlanadi.

    Kalit kodga (GitHub'ga) yozilmaydi: uni bilgan odam istalgan foydalanuvchi sessiyasini soxtalashtira oladi.
    """
    try:
        return path.read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        pass
    import secrets

    key = secrets.token_urlsafe(50)
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:  # boshqa jarayon shu lahzada yaratdi
        return path.read_text(encoding="utf-8").strip()
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        handle.write(key)
    return key


DEBUG = env_bool("DJANGO_DEBUG", False)
SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY") or secret_key_file(BASE_DIR / ".secret_key")

ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS", f"{SITE_DOMAIN},www.{SITE_DOMAIN},localhost,127.0.0.1,.localhost")
if DEBUG and ".localhost" not in ALLOWED_HOSTS:
    # Lokal SaaS sinovi: <otm>.localhost:8000 subdomenlari doim ochiq
    ALLOWED_HOSTS.append(".localhost")
CSRF_TRUSTED_ORIGINS = env_list("DJANGO_CSRF_TRUSTED_ORIGINS")
if not CSRF_TRUSTED_ORIGINS and not DEBUG:
    # Berilmagan bo'lsa ALLOWED_HOSTS dan: iqtidorasti.uz -> https://iqtidorasti.uz, .iqtidorasti.uz -> https://*.iqtidorasti.uz
    CSRF_TRUSTED_ORIGINS = [
        f"https://*{host}" if host.startswith(".") else f"https://{host}"
        for host in ALLOWED_HOSTS
        if host not in ("*", "localhost", "127.0.0.1") and not host.endswith("localhost")
    ]

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
elif os.environ.get("MYSQL_DATABASE"):
    # cPanel hostinglarida odatda MySQL/MariaDB beriladi. mysqlclient o'rnatilmasa, PyMySQL ishlatiladi
    try:
        import MySQLdb  # noqa: F401
    except ImportError:
        import pymysql

        pymysql.install_as_MySQLdb()
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.mysql",
            "NAME": os.environ["MYSQL_DATABASE"],
            "USER": os.environ.get("MYSQL_USER", ""),
            "PASSWORD": os.environ.get("MYSQL_PASSWORD", ""),
            "HOST": os.environ.get("MYSQL_HOST", "localhost"),
            "PORT": os.environ.get("MYSQL_PORT", "3306"),
            "CONN_MAX_AGE": 60,
            "OPTIONS": {"charset": "utf8mb4", "init_command": "SET sql_mode='STRICT_TRANS_TABLES'"},
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": Path(os.environ.get("SQLITE_PATH") or BASE_DIR / "db.sqlite3"),
            # Bir vaqtda ko'p yozuv kelganda «database is locked» bo'lmasligi uchun
            "OPTIONS": {"timeout": 20, "transaction_mode": "IMMEDIATE"},
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

CSRF_FAILURE_VIEW = "apps.web.views.public.csrf_failure"

LOGIN_URL = "web:login"
LOGIN_REDIRECT_URL = "web:dashboard"

STATIC_URL = "static/"
STATIC_ROOT = Path(os.environ.get("STATIC_ROOT") or BASE_DIR / "staticfiles")
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}
MEDIA_URL = "media/"
MEDIA_ROOT = Path(os.environ.get("MEDIA_ROOT") or BASE_DIR / "media")
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
SITE_URL = os.environ.get("SITE_URL", f"https://{SITE_DOMAIN}")

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
    # Production'da statik fayllarni gunicorn orqali whitenoise beradi (nginx bo'lsa, nginx o'zi beradi)
    MIDDLEWARE.insert(1, "whitenoise.middleware.WhiteNoiseMiddleware")
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    # HTTP -> HTTPS. Cookie'lar faqat https orqali saqlanadi: http da login va formalar «CSRF» xatosini beradi,
    # shuning uchun sayt http da ochilsa darhol https ga o'tkaziladi. SSL hali o'rnatilmagan bo'lsa: 0 qiling
    SECURE_SSL_REDIRECT = env_bool("DJANGO_SECURE_SSL_REDIRECT", True)
    # Sertifikat ishlayotganiga ishonch hosil qilgach yoqing, masalan 31536000 (1 yil)
    SECURE_HSTS_SECONDS = int(os.environ.get("DJANGO_HSTS_SECONDS", 0))
    SECURE_HSTS_INCLUDE_SUBDOMAINS = env_bool("DJANGO_HSTS_SUBDOMAINS", False)

# Xatolar: konsolga (gunicorn/systemd jurnali) va LOG_FILE berilsa faylga ham yoziladi
LOG_FILE = os.environ.get("LOG_FILE", "")
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {"plain": {"format": "{asctime} {levelname} {name}: {message}", "style": "{"}},
    "handlers": {
        "console": {"class": "logging.StreamHandler", "formatter": "plain"},
        **(
            {
                "file": {
                    "class": "logging.handlers.RotatingFileHandler",
                    "filename": LOG_FILE,
                    "maxBytes": 5 * 1024 * 1024,
                    "backupCount": 5,
                    "formatter": "plain",
                    "encoding": "utf-8",
                }
            }
            if LOG_FILE
            else {}
        ),
    },
    "root": {"handlers": ["console", *(["file"] if LOG_FILE else [])], "level": "WARNING"},
}
