#!/usr/bin/env bash
# cPanel serverida backend/.env faylini yaratadi (maxfiy kalit o'zi yaratiladi, baza ma'lumotlari so'raladi):
#   bash ~/iqtidorasti/deploy/cpanel_env.sh
set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
ENV_FILE="$REPO_DIR/backend/.env"
DOMAIN="${DOMAIN:-iqtidorasti.uz}"

if [ -n "${VIRTUAL_ENV:-}" ]; then
    PY="$VIRTUAL_ENV/bin/python"
else
    PY="$(ls -d "$HOME"/virtualenv/*/backend/*/bin/python 2>/dev/null | sort -V | tail -1 || true)"
    PY="${PY:-python3}"
fi

if [ -f "$ENV_FILE" ]; then
    read -r -p ".env allaqachon bor. Qaytadan yaratilsinmi? (ha/yo'q): " answer
    case "$answer" in ha|Ha|HA|y|Y|yes) cp "$ENV_FILE" "$ENV_FILE.bak.$(date +%s)" ;; *) echo "O'zgartirilmadi."; exit 0 ;; esac
fi

echo "cPanel → MySQL Databases bo'limida yaratgan baza ma'lumotlarini kiriting."
echo "MySQL hali yo'q bo'lsa, baza nomini bo'sh qoldiring: SQLite ishlatiladi (keyin MySQL'ga o'tish mumkin)."
read -r -p "Baza nomi (masalan, iqtidora_baza): " DB_NAME
DB_USER=""
DB_PASS=""
if [ -n "$DB_NAME" ]; then
    read -r -p "Baza foydalanuvchisi (masalan, iqtidora_user): " DB_USER
    read -r -s -p "Baza paroli (yozganingiz ko'rinmaydi): " DB_PASS
    echo
    "$PY" -c "import pymysql" 2>/dev/null || "$PY" -m pip install -q PyMySQL
fi

umask 077
ENV_FILE="$ENV_FILE" DOMAIN="$DOMAIN" DB_NAME="$DB_NAME" DB_USER="$DB_USER" DB_PASS="$DB_PASS" "$PY" - <<'PYEOF'
import os
import secrets


def quoted(value):
    # python-dotenv: bitta tirnoq ichida hech narsa o'zgarmaydi; tirnoqning o'zi bo'lsa, qo'sh tirnoq bilan qochiramiz
    if "'" not in value:
        return f"'{value}'"
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


env = os.environ
domain = env["DOMAIN"]
lines = [
    "DJANGO_DEBUG=0",
    f"DJANGO_SECRET_KEY={secrets.token_urlsafe(50)}",
    f"DJANGO_ALLOWED_HOSTS={domain},www.{domain}",
    f"SITE_URL=https://{domain}",
    f"MYSQL_DATABASE={env['DB_NAME']}",
    f"MYSQL_USER={env['DB_USER']}",
    f"MYSQL_PASSWORD={quoted(env['DB_PASS'])}",
    "MYSQL_HOST=localhost",
    "AUDIT_TRUST_X_FORWARDED_FOR=0",
    "REGISTRATION_OPEN=1",
    "SPONSOR_CONTACT=@abdujalil_chirmashev",
]
with open(env["ENV_FILE"], "w", encoding="utf-8") as handle:
    handle.write("\n".join(lines) + "\n")
PYEOF
chmod 600 "$ENV_FILE"

echo "Tekshirilmoqda..."
cd "$REPO_DIR/backend"
if "$PY" manage.py check --deploy --fail-level ERROR >/dev/null 2>&1 && "$PY" -c "
import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()
from django.db import connection
connection.ensure_connection()
"; then
    echo "TAYYOR: .env yaratildi va bazaga ulanildi. Endi:"
    echo "  python manage.py migrate && python manage.py collectstatic --noinput && python manage.py seed"
    echo "  python manage.py createsuperuser"
else
    echo "!! .env yaratildi, lekin bazaga ulanib bo'lmadi. Baza nomi, foydalanuvchi va parolni tekshirib,"
    echo "   skriptni qayta ishga tushiring (cPanel'da foydalanuvchi bazaga ALL PRIVILEGES bilan qo'shilgan bo'lsin)."
    exit 1
fi
