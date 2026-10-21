#!/usr/bin/env bash
# cPanel hostingda yangi versiyani o'rnatish (cPanel → Terminal):
#   bash ~/iqtidorasti/deploy/cpanel_update.sh
# GitHub'dan yangi kodni oladi, kutubxonalar, migratsiya va statik fayllarni yangilaydi va ilovani qayta ishga tushiradi.
set -euo pipefail

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

echo "== Kod: GitHub'dan yangilanmoqda"
git -C "$REPO_DIR" pull --ff-only
echo "== Kutubxonalar"
"$PY" -m pip install -q -r "$APP/requirements.txt" PyMySQL
cd "$APP"
echo "== Ma'lumotlar bazasi"
"$PY" manage.py migrate --noinput
echo "== Statik fayllar"
"$PY" manage.py collectstatic --noinput -v 0
mkdir -p "$APP/tmp" && touch "$APP/tmp/restart.txt"   # Passenger ilovani qayta ishga tushiradi
echo "TAYYOR: $(git -C "$REPO_DIR" log --oneline -1)"
