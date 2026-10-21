#!/usr/bin/env bash
# cPanel hostingda yangi versiyani o'rnatish (cPanel → Terminal):
#   bash ~/iqtidorasti/deploy/cpanel_update.sh
# GitHub'dan yangi kodni oladi, kutubxonalar, migratsiya va statik fayllarni yangilaydi va ilovani qayta ishga tushiradi.
#
# Avtomatik yangilash (cPanel → Cron Jobs, har 15 daqiqada):
#   bash $HOME/iqtidorasti/deploy/cpanel_update.sh --auto >> $HOME/iqtidorasti-update.log 2>&1
# --auto rejimida GitHub'da yangi versiya bo'lmasa, hech narsa qilmasdan chiqadi.
set -euo pipefail
AUTO=0
[ "${1:-}" = "--auto" ] && AUTO=1

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
APP="$REPO_DIR/backend"

# «Setup Python App» yaratgan virtual muhit: ~/virtualenv/<ilova papkasi>/<versiya>/bin/python
if [ -n "${VIRTUAL_ENV:-}" ]; then
    PY="$VIRTUAL_ENV/bin/python"
else
    PY="$(ls -d "$HOME"/virtualenv/*/backend/*/bin/python 2>/dev/null | sort -V | tail -1 || true)"
fi
if [ -z "$PY" ] || [ ! -x "$PY" ]; then
    echo "Python muhiti topilmadi. Setup Python App sahifasidagi 'source .../bin/activate' buyrug'ini bajarib, qayta urinib ko'ring."
    exit 1
fi

git -C "$REPO_DIR" fetch -q origin
if [ "$(git -C "$REPO_DIR" rev-parse HEAD)" = "$(git -C "$REPO_DIR" rev-parse '@{u}')" ]; then
    [ "$AUTO" = 1 ] && exit 0   # yangi versiya yo'q
    echo "Kod allaqachon eng so'nggi versiyada: baribir migratsiya va statik fayllar tekshiriladi"
fi
echo "== $(date '+%F %T') Kod: GitHub'dan yangilanmoqda"
git -C "$REPO_DIR" merge -q --ff-only '@{u}'
echo "== Kutubxonalar"
"$PY" -m pip install -q -r "$APP/requirements.txt" PyMySQL
cd "$APP"
echo "== Ma'lumotlar bazasi"
"$PY" manage.py migrate --noinput
echo "== Statik fayllar"
"$PY" manage.py collectstatic --noinput -v 0
mkdir -p "$APP/tmp" && touch "$APP/tmp/restart.txt"   # Passenger ilovani qayta ishga tushiradi
echo "TAYYOR: $(git -C "$REPO_DIR" log --oneline -1)"
