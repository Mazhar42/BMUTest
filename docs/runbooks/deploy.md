# Runbook — deploying BMU Lab to a VPS

Audience: whoever operates the server. Design: [ADR 0004](../adr/0004-deployment.md).

> **Not yet for real patients.** The pilot goes live after **M9** (ROADMAP §10). Until then, deploy only to
> a staging/demo server. Real SMS, payments, catalog and hosting are open **[BMU]** items (PROGRESS.md).

## How it fits together

```
git push main ──► CI: tests + Playwright ──► images on GHCR (sha-xxxxxxx, latest)
                                               │
Actions ▸ Deploy ▸ Run workflow (tag) ──► approval on "production" environment
                                               │
                         ssh ──► /opt/bmu-lab/deploy.sh <tag>
                                  pull → pg_dump → alembic upgrade → restart → health check
```

On the server: `postgres`, `redis`, `minio` (RustFS), `api`, `worker`, `beat` and `web` (Caddy: TLS, patient
PWA at `/`, staff app at `/staff/`, `/api` proxy). Only ports 80/443 are published.

## 1. One-time server setup (Ubuntu 22.04/24.04 LTS)

```bash
# as root
apt-get update && apt-get -y upgrade
curl -fsSL https://get.docker.com | sh
adduser --disabled-password --gecos "" deploy
usermod -aG docker deploy
mkdir -p /opt/bmu-lab && chown deploy:deploy /opt/bmu-lab
ufw allow OpenSSH && ufw allow 80/tcp && ufw allow 443/tcp && ufw allow 443/udp && ufw --force enable
```

DNS: point an `A` record (e.g. `lab.example.org`) at the server **before** the first deploy, so Caddy can
obtain the certificate.

SSH key for GitHub Actions (on your machine):

```bash
ssh-keygen -t ed25519 -f bmu-deploy -C "github-actions-deploy" -N ""
ssh-copy-id -i bmu-deploy.pub deploy@<server>
ssh-keyscan <server>            # → value for VPS_KNOWN_HOSTS
```

## 2. Server secrets: `/opt/bmu-lab/.env`

Copy [`deploy/.env.production.example`](../../deploy/.env.production.example) to `/opt/bmu-lab/.env`
(the first deploy also copies the example there) and fill in every value:

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(48))"        # JWT_SECRET, POSTGRES_PASSWORD, S3_SECRET_KEY
docker run --rm python:3.12-slim sh -c "pip -q install cryptography && python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'"   # APP_ENCRYPTION_KEY
chmod 600 /opt/bmu-lab/.env
```

`REGISTRY` must be `ghcr.io/<github-owner-in-lowercase>`. The API refuses to start with `ENV=prod` and any
development secret, or with `COOKIE_SECURE=false`.

**Keep a copy of `APP_ENCRYPTION_KEY` somewhere safe** — without it, encrypted NID numbers and staff TOTP
secrets cannot be read.

## 3. GitHub settings (repository → Settings)

| Where | Name | Value |
|---|---|---|
| Environments | `production` | add **Required reviewers** (this is the manual approval gate) |
| Environment secrets | `VPS_HOST` | server IP or hostname |
| | `VPS_USER` | `deploy` |
| | `VPS_SSH_KEY` | contents of the private key `bmu-deploy` |
| | `VPS_KNOWN_HOSTS` | output of `ssh-keyscan <server>` |
| | `VPS_PORT` | optional, default 22 |
| Environment variables | `PUBLIC_URL` | `https://lab.example.org` (used for the smoke test) |
| | `VPS_PATH` | optional, default `/opt/bmu-lab` |
| Actions → General | Workflow permissions | read (the workflows request `packages: write/read` themselves) |

Images are pushed to GHCR by CI; the deploy job logs the server into GHCR with its short-lived token.

## 4. Deploying

1. Merge to `main`. Wait for **CI** to finish green; the run summary shows the image tag (`sha-xxxxxxx`).
2. **Actions → Deploy → Run workflow**, enter the tag, run, then approve the `production` environment.
   Or push a version tag (`git tag v0.3.0 && git push --tags`); after CI passes, the deploy waits for approval.
3. The job prints `OK: <tag> is live` and the smoke test calls `https://<domain>/api/v1/health`.

First deploy only:

```bash
ssh deploy@<server>
cd /opt/bmu-lab
docker compose -f docker-compose.prod.yml run --rm api python -m app.cli seed            # PLACEHOLDER catalog
docker compose -f docker-compose.prod.yml run --rm api python -m app.cli create-superadmin
```

Do **not** run `seed --demo` on a real server (it creates demo staff with a shared password).
The super admin enrols an authenticator app at first login, then creates the other staff accounts.

## 5. Rollback

`deploy.sh` prints the previous tag. To roll back: Run workflow with that tag. If the release you are
leaving contained a database migration, first restore the pre-deploy dump that `deploy.sh` wrote:

```bash
cd /opt/bmu-lab
docker compose -f docker-compose.prod.yml stop api worker beat
docker compose -f docker-compose.prod.yml exec -T postgres pg_restore -U bmu -d bmu --clean --if-exists < backups/pre-<tag>-<time>.dump
./deploy.sh <previous-tag>
```

## 6. Backups (interim until M9)

```bash
crontab -e   # as deploy
30 2 * * * /opt/bmu-lab/backup.sh >> /opt/bmu-lab/backups/backup.log 2>&1
```

`backup.sh` keeps 14 days of database dumps and object-store archives in `/opt/bmu-lab/backups`.
Copy them off the server. M9 adds WAL shipping, an object-store mirror and a tested restore drill.

## 7. Useful commands

```bash
cd /opt/bmu-lab
docker compose -f docker-compose.prod.yml ps
docker compose -f docker-compose.prod.yml logs -f --tail 100 api worker
docker compose -f docker-compose.prod.yml exec postgres psql -U bmu bmu
cat .deployed_tag .previous_tag
```

## Local production-like check

`make up-prod` (or `./make.ps1 up-prod`) builds the same web image and serves it at http://localhost:8090
against the dev API.
