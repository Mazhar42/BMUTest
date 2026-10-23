# BMU Lab — Digital Laboratory Service & Queue Management

One order code, one backend, every channel: patients register, get their tests verified, pay, give a
sample and download their report — online (PWA + SMS) or through staff counters that print the same
3-part slip BMU uses today.

- **Status:** milestones M1–M4 done (foundation; catalog, patients, OTP login; prescriptions, orders,
  verification, waivers, 3-part slip; payments: bank teller, counter cash, online gateway, refunds,
  reconciliation). Next: M5 scheduling and queue. See [docs/PROGRESS.md](docs/PROGRESS.md).
- **Plan:** [docs/ROADMAP.md](docs/ROADMAP.md) · **Decisions:** [docs/adr/](docs/adr/) ·
  **Deploying:** [docs/runbooks/deploy.md](docs/runbooks/deploy.md)

> Catalog contents, prices and preparation text in `backend/seed/` are **placeholders** until confirmed by
> the BMU laboratory. The software never interprets results.

## Quick start (Docker + Node 22 + pnpm 9)

```bash
cp .env.example .env
make up && make migrate && make seed      # Windows: ./make.ps1 up | migrate | seed
make web                                   # patient http://localhost:5173 · staff http://localhost:5174/staff/
make check                                 # lint + types + tests (backend and frontend)
make e2e                                   # Playwright golden paths
```

Demo staff password: `bmu-demo-2026` (usernames printed by `make seed`, e.g. `helpdesk`, `verifier`).
In development the patient OTP is shown on screen (mock SMS).

## Stack

FastAPI · SQLAlchemy 2 · PostgreSQL 16 · Celery/Redis · S3 object store · WeasyPrint · React 18 + Vite +
Tailwind · TanStack Query · Playwright · GitHub Actions → GHCR → Docker Compose + Caddy on a VPS.
