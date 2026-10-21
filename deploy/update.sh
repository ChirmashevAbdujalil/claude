#!/usr/bin/env bash
# Yangi versiyani o'rnatish: sudo bash /srv/iqtidorasti/app/deploy/update.sh
set -euo pipefail
APP=/srv/iqtidorasti/app
VENV=/srv/iqtidorasti/venv
APP_USER=iqtidor

/usr/local/bin/iqtidorasti-backup || echo "!! Zaxira nusxa olinmadi, davom etilmoqda"
sudo -u "$APP_USER" git -C "$APP" pull --ff-only
sudo -u "$APP_USER" "$VENV/bin/pip" install -q -r "$APP/backend/requirements.txt"
cd "$APP/backend"
sudo -u "$APP_USER" "$VENV/bin/python" manage.py migrate --noinput
sudo -u "$APP_USER" "$VENV/bin/python" manage.py collectstatic --noinput -v 0
systemctl restart iqtidorasti
echo "Yangilandi: $(git -C "$APP" log --oneline -1)"
