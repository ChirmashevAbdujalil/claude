#!/usr/bin/env bash
# Kunlik zaxira: ma'lumotlar bazasi va yuklangan fayllar. 14 kundan eskilari o'chiriladi.
set -euo pipefail
ROOT=/srv/iqtidorasti
DEST="$ROOT/backups"
STAMP="$(date +%Y%m%d-%H%M)"
mkdir -p "$DEST"
sudo -u postgres pg_dump -Fc iqtidorasti > "$DEST/db-$STAMP.dump"
tar -czf "$DEST/files-$STAMP.tar.gz" -C "$ROOT/app/backend" media private_media 2>/dev/null || true
find "$DEST" -type f -mtime +14 -delete
echo "$(date '+%F %T') zaxira: $DEST/db-$STAMP.dump"
