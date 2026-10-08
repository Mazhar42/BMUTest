# BMU Lab — Digital Laboratory Service & Queue Management

One code, one backend, every channel: patients register, get verified, pay, book an
arrival window, give a sample and download their report — online (PWA + SMS) or through
staff counters that print the same 3-part slip BMU uses today.

- Roadmap (source of truth): [docs/ROADMAP.md](docs/ROADMAP.md)
- What's built / deviations / open questions: [docs/PROGRESS.md](docs/PROGRESS.md)
- Architecture decisions: [docs/adr/](docs/adr/)

## Commands
| | Linux/macOS (`make`) | Windows (`./make.ps1`) |
|---|---|---|
| Start stack (db, redis, minio, api, worker, beat) | `make up` | `./make.ps1 up` |
| Apply migrations | `make migrate` | `./make.ps1 migrate` |
| Demo data (catalog, staff for every role, capacity) | `make seed` | `./make.ps1 seed` |
| Lint + typecheck + tests (backend + frontend) | `make check` | `./make.ps1 check` |
| Playwright golden paths | `make e2e` | `./make.ps1 e2e` |
| Regenerate the TS API client | `make gen-api` | `./make.ps1 gen-api` |
| Frontend dev servers (patient :5173, staff :5174) | `make web` | `./make.ps1 web` |
| Production-like stack (built apps via Caddy, :8090) | `make up-prod` | `./make.ps1 up-prod` |

Deploys: CI pushes images to GHCR; **Actions → Deploy** (manual approval) runs `deploy/deploy.sh` on the VPS —
see [docs/runbooks/deploy.md](docs/runbooks/deploy.md). PDF/barcode tests (`tests/pdf`) need the Docker image:
`docker compose run --rm api pytest tests/pdf`.

## Working rules (from ROADMAP §0.1)
1. Milestones in order; vertical slices (backend + staff UI + patient UI + tests + seed).
2. Definition of done: acceptance criteria pass, `make check` green, Alembic migration included, `docs/PROGRESS.md` updated.
3. **Never invent medical or financial content.** Prices, fasting, prep text, reference ranges, tubes, TATs live in `backend/seed/` files headed `PLACEHOLDER — must be confirmed by BMU laboratory`. The software never interprets results.
4. **Every status change goes through `app.core.state_machine.transition()`** — never assign `.status` directly.
5. Decisions not covered by the roadmap → simplest option, recorded as `docs/adr/NNNN-title.md`.
6. `[BMU]` items: build behind a config flag/adapter with a mock; list the open item in PROGRESS.md.
7. Secrets only in `.env` (never committed); `.env.example` lists every key.

## Layout
```
backend/app/core/        codes, state_machine, security, audit, i18n, errors, clock, events
backend/app/modules/<m>/ models.py schemas.py service.py router_patient.py router_staff.py tasks.py
backend/seed/            PLACEHOLDER catalog / capacity / reference ranges
frontend/apps/patient    PWA (bn default)          frontend/apps/staff  all staff roles + /display + /kiosk
frontend/packages/       ui (design system), i18n (bn.json/en.json), api-client (generated)
e2e/                     Playwright golden paths
```

## Conventions
- **Python:** ruff, mypy strict on `app/`, SQLAlchemy 2.0 typed models (`Mapped[...]`), Pydantic v2
  schemas separate from ORM models. Services hold business logic; routers stay thin and call
  `db.commit()` after a mutating service call. Money = integer paisa. Time stored UTC, business
  day = Asia/Dhaka (`app.core.clock`). Errors are `AppError(code, message_key, params)`.
- **TypeScript:** strict, no `any`, TanStack Query for server state, API client generated from
  FastAPI OpenAPI (`openapi-typescript` + `openapi-fetch`).
- **UI text only via i18n keys** (`packages/i18n/src/{bn,en}.json`); backend errors carry `message_key`.
