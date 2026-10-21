#!/usr/bin/env bash
# iqtidorasti.uz ni toza Ubuntu 22.04/24.04 VPS'ga o'rnatish (root sifatida ishga tushiring):
#   EMAIL=siz@pochta.uz bash install_vps.sh
# Qayta ishga tushirsa ham xavfsiz: bor narsalarni buzmaydi, faqat yetishmaganini qo'shadi.
set -euo pipefail

DOMAIN="${DOMAIN:-iqtidorasti.uz}"
EMAIL="${EMAIL:-}"                       # SSL sertifikati uchun (Let's Encrypt)
REPO="${REPO:-https://github.com/ChirmashevAbdujalil/claude.git}"   # yoki claude.bundle fayl yo'li
BRANCH="${BRANCH:-claude/salom-dasturchi-startuper-48z19p}"
APP_USER=iqtidor
ROOT=/srv/iqtidorasti
APP="$ROOT/app"
VENV="$ROOT/venv"
DB_NAME=iqtidorasti

[ "$(id -u)" -eq 0 ] || { echo "root sifatida ishga tushiring: sudo bash $0"; exit 1; }

echo "== 1/8 Kerakli dasturlar"
export DEBIAN_FRONTEND=noninteractive
apt-get update -q
apt-get install -y -q python3 python3-venv python3-dev build-essential libpq-dev git nginx \
    postgresql postgresql-contrib certbot python3-certbot-nginx openssl

echo "== 2/8 Foydalanuvchi va papkalar"
id -u "$APP_USER" >/dev/null 2>&1 || useradd --system --create-home --home-dir "$ROOT" --shell /bin/bash "$APP_USER"
mkdir -p "$ROOT/logs" "$ROOT/backups"
chown -R "$APP_USER:$APP_USER" "$ROOT"
chmod 755 "$ROOT"   # nginx statik fayllarni o'qiy olishi uchun

echo "== 3/8 Kod"
if [ -d "$APP/.git" ]; then
    sudo -u "$APP_USER" git -C "$APP" pull --ff-only
else
    sudo -u "$APP_USER" git clone --branch "$BRANCH" "$REPO" "$APP"
fi
chmod 755 "$APP" "$APP/backend"

echo "== 4/8 Python muhiti"
[ -d "$VENV" ] || sudo -u "$APP_USER" python3 -m venv "$VENV"
sudo -u "$APP_USER" "$VENV/bin/pip" install -q --upgrade pip
sudo -u "$APP_USER" "$VENV/bin/pip" install -q -r "$APP/backend/requirements.txt"

echo "== 5/8 PostgreSQL va .env"
ENV_FILE="$APP/backend/.env"
if [ ! -f "$ENV_FILE" ]; then
    DB_PASS="$(openssl rand -hex 24)"
    SECRET="$(python3 -c 'import secrets; print(secrets.token_urlsafe(50))')"
    sudo -u postgres psql -qc "CREATE USER $APP_USER WITH PASSWORD '$DB_PASS';" 2>/dev/null \
        || sudo -u postgres psql -qc "ALTER USER $APP_USER WITH PASSWORD '$DB_PASS';"
    sudo -u "$APP_USER" bash -c "cat > '$ENV_FILE'" <<ENV
DJANGO_DEBUG=0
DJANGO_SECRET_KEY=$SECRET
DJANGO_ALLOWED_HOSTS=$DOMAIN,www.$DOMAIN
SITE_URL=https://$DOMAIN
POSTGRES_DB=$DB_NAME
POSTGRES_USER=$APP_USER
POSTGRES_PASSWORD=$DB_PASS
POSTGRES_HOST=localhost
AUDIT_TRUST_X_FORWARDED_FOR=1
LOG_FILE=$ROOT/logs/django.log
REGISTRATION_OPEN=1
SPONSOR_CONTACT=@abdujalil_chirmashev
ENV
    chmod 600 "$ENV_FILE"
fi
sudo -u postgres psql -tAc "SELECT 1 FROM pg_database WHERE datname='$DB_NAME'" | grep -q 1 \
    || sudo -u postgres createdb -O "$APP_USER" -E UTF8 "$DB_NAME"

echo "== 6/8 Django: migratsiya, statik fayllar, boshlang'ich ma'lumotlar"
cd "$APP/backend"
sudo -u "$APP_USER" "$VENV/bin/python" manage.py migrate --noinput
sudo -u "$APP_USER" "$VENV/bin/python" manage.py collectstatic --noinput -v 0
sudo -u "$APP_USER" "$VENV/bin/python" manage.py seed

echo "== 7/8 gunicorn (systemd) va nginx"
cp "$APP/deploy/iqtidorasti.service" /etc/systemd/system/iqtidorasti.service
systemctl daemon-reload
systemctl enable --now iqtidorasti
systemctl restart iqtidorasti
cp "$APP/deploy/nginx-iqtidorasti.uz.conf" /etc/nginx/sites-available/iqtidorasti.uz
ln -sf /etc/nginx/sites-available/iqtidorasti.uz /etc/nginx/sites-enabled/iqtidorasti.uz
rm -f /etc/nginx/sites-enabled/default
nginx -t
systemctl reload nginx

echo "== 8/8 SSL va kunlik zaxira nusxa"
if [ -n "$EMAIL" ]; then
    certbot --nginx -d "$DOMAIN" -d "www.$DOMAIN" --non-interactive --agree-tos -m "$EMAIL" --redirect || \
        echo "!! SSL olinmadi: DNS (A yozuvlar) serverga qaraganini tekshirib, keyinroq qayta ishga tushiring"
else
    echo "!! EMAIL berilmadi: SSL keyin qo'lda: certbot --nginx -d $DOMAIN -d www.$DOMAIN --redirect"
fi
install -m 755 "$APP/deploy/backup.sh" /usr/local/bin/iqtidorasti-backup
echo "30 3 * * * root /usr/local/bin/iqtidorasti-backup >> $ROOT/logs/backup.log 2>&1" > /etc/cron.d/iqtidorasti-backup

echo
echo "TAYYOR: https://$DOMAIN"
echo "Endi administrator akkaunti yarating:"
echo "  cd $APP/backend && sudo -u $APP_USER $VENV/bin/python manage.py createsuperuser"
