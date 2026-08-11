#!/usr/bin/env bash
# The only command you should ever run to update the live site:
#   ./deploy/deploy.sh
#
# Pulls whatever is currently on `main` in GitHub, rebuilds, and restarts.
# Never edit files directly on this server — anything not pushed to `main`
# and pulled through this script does not exist the next time this runs, and
# there is no record of what it was.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

ENV_FILE="$REPO_ROOT/deploy/production.env"
if [ ! -f "$ENV_FILE" ]; then
  echo "Missing $ENV_FILE — copy production.env.example and fill it in first." >&2
  exit 1
fi

if [ -n "$(git status --porcelain)" ]; then
  echo "This checkout has local changes that were never pushed to GitHub:" >&2
  git status --short >&2
  echo "Resolve that first (either push them from your laptop, or discard them here) — deploy.sh refuses to run over uncommitted state." >&2
  exit 1
fi

echo "Fetching latest main..."
git fetch origin main
git reset --hard origin/main

echo "Building images..."
docker compose -f deploy/docker-compose.prod.yml --env-file "$ENV_FILE" build

echo "Migrating, collecting static files, and restarting (the api container runs both on start)..."
docker compose -f deploy/docker-compose.prod.yml --env-file "$ENV_FILE" up -d

echo "Removing now-unused images from previous deploys..."
docker image prune -f

echo "Status:"
docker compose -f deploy/docker-compose.prod.yml --env-file "$ENV_FILE" ps

echo "Done. Tail logs with:"
echo "  docker compose -f deploy/docker-compose.prod.yml --env-file deploy/production.env logs -f"
