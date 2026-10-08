# 0004 — Deployment: CI-built images, Caddy front door, manually approved deploys

**Status:** accepted (M1–M3 infrastructure)

## Context
The roadmap targets Docker Compose on an Ubuntu VPS with TLS. Deploys must be repeatable, reversible
and must never happen by accident while the system is not yet production-ready.

## Decision
- **CI** (`.github/workflows/ci.yml`): backend lint/types/migrations/tests (including slip PDF barcode
  decoding), frontend lint/types/tests/build, Playwright golden paths, then — on `main` and `v*` tags only —
  builds and pushes `bmu-lab-api` and `bmu-lab-web` to GHCR tagged `sha-<7>` (+ `latest` / version).
- **Front door:** Caddy (`deploy/web`) instead of nginx. It serves the patient PWA at `/`, the staff app at
  `/staff/`, proxies `/api`, and obtains/renews Let's Encrypt certificates itself; it also sets CSP/HSTS.
  This removes certbot cron jobs and a second proxy. One origin keeps the refresh cookie first-party.
- **Deploy** (`.github/workflows/deploy.yml`): only via "Run workflow" with an image tag, or proposed after
  CI passes on a `v*` tag; always waits for approval on the GitHub `production` environment. On the server,
  `deploy/deploy.sh` pulls, takes a pre-deploy `pg_dump`, runs `alembic upgrade head`, restarts and waits
  for `/api/v1/health`.
- The API refuses to start with `ENV=prod` and development secrets (`check_production`).

## Consequences
Rollback = redeploy the previous tag (printed by `deploy.sh`); a rollback across a migration needs the
pre-deploy dump (runbook). Secrets live only in `/opt/bmu-lab/.env` on the server.
