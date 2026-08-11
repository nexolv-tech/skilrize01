#!/usr/bin/env bash
# Dumps the database and the uploaded-files volume, ships both off this VM to
# Backblaze B2, then prunes old local copies. Meant to run nightly via cron —
# see deploy/crontab.example.
#
# Why this exists: Postgres data and uploaded files both live only on this
# one VM's disk right now. If the instance is ever reclaimed, corrupted, or
# just has a bad disk day, everything in it is gone with no way back. This
# script is that way back.
#
# Requires `rclone` on the VM (apt-get install rclone) and B2_* filled in in
# production.env. Uses rclone's "on the fly" remote syntax so no separate
# rclone.conf with duplicated secrets is needed — production.env stays the
# one place credentials live.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="$REPO_ROOT/deploy/production.env"
COMPOSE=(docker compose -f "$REPO_ROOT/deploy/docker-compose.prod.yml" --env-file "$ENV_FILE")

if [ ! -f "$ENV_FILE" ]; then
  echo "Missing $ENV_FILE — copy production.env.example and fill it in first." >&2
  exit 1
fi

# shellcheck disable=SC1090
set -a; source "$ENV_FILE"; set +a

for var in POSTGRES_USER POSTGRES_DB B2_BUCKET B2_ACCOUNT_ID B2_APPLICATION_KEY; do
  if [ -z "${!var:-}" ]; then
    echo "production.env is missing $var — cannot back up." >&2
    exit 1
  fi
done

TIMESTAMP=$(date +%Y%m%d-%H%M%S)
BACKUP_DIR="$REPO_ROOT/deploy/backups"
mkdir -p "$BACKUP_DIR"

DB_DUMP="$BACKUP_DIR/db-$TIMESTAMP.sql.gz"
STORAGE_TAR="$BACKUP_DIR/storage-$TIMESTAMP.tar.gz"

echo "[$TIMESTAMP] Dumping database..."
"${COMPOSE[@]}" exec -T db pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB" | gzip > "$DB_DUMP"

echo "[$TIMESTAMP] Archiving uploaded files..."
# The volume name is Compose's default <project>_<volume> pattern, derived
# from `name: skilrize-prod` in docker-compose.prod.yml.
docker run --rm \
  -v skilrize-prod_api-storage:/data:ro \
  -v "$BACKUP_DIR":/backup \
  alpine tar czf "/backup/storage-$TIMESTAMP.tar.gz" -C /data .

B2_REMOTE=":b2,account=${B2_ACCOUNT_ID},key=${B2_APPLICATION_KEY}:${B2_BUCKET}"

echo "[$TIMESTAMP] Uploading to Backblaze B2..."
rclone copy "$DB_DUMP" "$B2_REMOTE/db/"
rclone copy "$STORAGE_TAR" "$B2_REMOTE/storage/"

echo "[$TIMESTAMP] Pruning local copies older than 7 days (B2 holds the long-term history — set a lifecycle rule on the bucket if you want it to expire too)..."
find "$BACKUP_DIR" -type f -mtime +7 -delete

echo "[$TIMESTAMP] Backup complete."
