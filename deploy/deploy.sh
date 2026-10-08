#!/usr/bin/env bash
# Runs ON THE VPS (called by .github/workflows/deploy.yml, or by hand):  ./deploy.sh <image-tag>
# Pulls the CI-built images, backs up the database, applies migrations, restarts, waits for health.
# Roll back with ./deploy.sh <previous-tag> (printed at the end; migrations are forward-only, so a
# rollback across a schema change needs the pre-deploy backup — see docs/runbooks/deploy.md).
set -euo pipefail

TAG="${1:?usage: deploy.sh <image-tag>}"
cd "$(dirname "$0")"
COMPOSE="docker compose -f docker-compose.prod.yml"

[ -f .env ] || { echo "ERROR: $(pwd)/.env is missing (copy .env.production.example and fill it in)"; exit 1; }
export TAG

PREVIOUS="$(cat .deployed_tag 2>/dev/null || echo none)"
echo "==> deploying ${TAG} (previous: ${PREVIOUS})"

$COMPOSE pull
$COMPOSE up -d postgres redis minio

echo "==> waiting for postgres"
for _ in $(seq 1 60); do
  $COMPOSE exec -T postgres pg_isready -U bmu -d bmu >/dev/null 2>&1 && break
  sleep 2
done

if [ "${PREVIOUS}" != "none" ]; then
  echo "==> pre-deploy backup"
  mkdir -p backups
  $COMPOSE exec -T postgres pg_dump -U bmu -d bmu --format=custom > "backups/pre-${TAG}-$(date +%Y%m%d%H%M%S).dump"
fi

echo "==> migrations"
$COMPOSE run --rm --no-deps api alembic upgrade head

echo "==> starting services"
$COMPOSE up -d --remove-orphans

echo "==> waiting for the API to be healthy"
for _ in $(seq 1 60); do
  if $COMPOSE exec -T api curl -fs http://localhost:8000/api/v1/health >/dev/null 2>&1; then
    echo "${TAG}" > .deployed_tag
    echo "${PREVIOUS}" > .previous_tag
    docker image prune -f >/dev/null
    echo "==> OK: ${TAG} is live. Roll back with: ./deploy.sh ${PREVIOUS}"
    exit 0
  fi
  sleep 3
done
echo "ERROR: API did not become healthy. Logs:"
$COMPOSE logs --tail 80 api
exit 1
