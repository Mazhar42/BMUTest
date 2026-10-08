#!/usr/bin/env bash
# Nightly backup ON THE VPS (cron: 30 2 * * * /opt/bmu-lab/backup.sh). Keeps 14 days locally;
# copy backups/ off the server as well (ROADMAP M9 adds WAL shipping, object-store mirror and restore drills).
set -euo pipefail
cd "$(dirname "$0")"
COMPOSE="docker compose -f docker-compose.prod.yml"
mkdir -p backups
STAMP="$(date +%Y%m%d-%H%M%S)"
$COMPOSE exec -T postgres pg_dump -U bmu -d bmu --format=custom > "backups/bmu-${STAMP}.dump"
docker run --rm -v bmu-lab_objects:/data:ro -v "$(pwd)/backups:/out" alpine tar czf "/out/objects-${STAMP}.tgz" -C /data .
find backups -type f -mtime +14 -delete
echo "backup ok: ${STAMP}"
