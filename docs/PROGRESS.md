# Progress

What is built, how it maps to the acceptance criteria, deviations, and open questions.
Source of truth for scope: [ROADMAP.md](ROADMAP.md). Decisions: [adr/](adr/).

| Milestone | Status |
|---|---|
| M0 Discovery & baseline [BMU] | Open — institutional work; catalog/prices/prep in `backend/seed/` are **PLACEHOLDER** |
| **M1 Foundation** | **Done** |
| **M2 Catalog, patients, patient login** | **Done** |
| **M3 Prescriptions, orders, 3-part slip** | **Done** |
| M4 Payments | Next. The `payment` table, its state machine and the WAIVER method already exist |
| M5–M9 | Not started (screens show "arrives in M*n*" in the staff navigation) |

Deployment pipeline (CI → GHCR → manually approved VPS deploy) is in place: [runbooks/deploy.md](runbooks/deploy.md).

## How to verify

```bash
make up && make migrate && make seed     # ./make.ps1 … on Windows
make check                               # backend: ruff, format, mypy, pytest · frontend: lint, typecheck, vitest
make e2e                                 # Playwright golden paths (starts both Vite dev servers)
```

Demo staff (from `make seed`, password `bmu-demo-2026`): `helpdesk`, `verifier`, `waiver`, `labadmin`,
`admin`, … — roles needing TOTP (`admin`, `labadmin`, `patho`, `waiver`) enrol an authenticator at first
login. Patient app: http://localhost:5173 (in dev the OTP is shown on screen), staff app:
http://localhost:5174/staff/.

## M1 — Foundation

Built: repo scaffold, docker-compose, Makefile + `make.ps1`, `.env.example`, config, DB session, error model
`{code, message_key, params}`, JSON logging with PII masking, `/api/v1/health`, injectable clock
(Asia/Dhaka), `core/codes.py` (Damm), generic state machine + audit + domain events, append-only
`audit_log` trigger, staff auth (argon2 password, TOTP enrol/verify, 12 h session, 30 min idle lock,
lockout after 5 failures, station recorded), roles → permissions, `require()`, `create-superadmin` CLI,
frontend workspace (`ui`, `i18n` bn/en with per-user language, generated `api-client`), staff app shell
with login (password → TOTP enrol/verify), lock screen, role-based navigation; patient PWA shell.
CI: [.github/workflows/ci.yml](../.github/workflows/ci.yml).

| Acceptance | Evidence |
|---|---|
| `make up && make migrate && make check` from a clean clone | CI `backend` + `frontend` jobs; `alembic check` proves migrations match models |
| Staff user logs in with TOTP | `test_pathologist_must_enrol_totp_then_login_with_totp`; staff `LoginPage` |
| Damm 572→4, every single-digit mutation rejected, round trip | `tests/unit/test_codes.py` |
| UPDATE on `audit_log` fails at DB level | `test_audit_log_update_and_delete_fail_at_db_level` |

## M2 — Catalog, patients, patient login

Built: catalog models + admin CRUD API and screens (tests, departments, price change with history,
active flag), idempotent CSV import (API + upload screen + `make seed`), alias search (prefix match per
word + pg_trgm fallback, Bangla and English); patient OTP login (hashed code, TTL, attempts, per-mobile
and per-IP rate limits, mock SMS), 15-min access JWT + rotating httpOnly refresh cookie with reuse
detection and CSRF header; account, family profiles (DOB **or** age); staff patient search (mobile in any
format incl. Bangla digits, name, hospital no., order code) with duplicate warning; SMS outbox with
bn/en templates, retry/backoff and Beat delivery. PWA: welcome/language, OTP login, home with three
buttons, "Who is this for?", add family member.

| Acceptance | Evidence |
|---|---|
| Importing the seed CSV twice is idempotent | `test_import_twice_is_idempotent`, `test_admin_crud_and_csv_upload` |
| "s creat" finds Creatinine, in Bangla and English | `test_search_matches_aliases_in_english` / `_in_bangla` |
| OTP rate limits enforced | `test_otp_rate_limit_per_mobile`, `test_otp_rate_limit_per_ip`, `test_otp_max_attempts_and_expiry` |
| Patient can't access another account's patients | `test_patient_cannot_access_another_accounts_patients`, `test_orders_are_isolated_between_accounts` |

## M3 — Prescriptions, orders, the 3-part slip

Built: prescription upload (1–3 images, client-side compression to ≤ 1 MB, server magic-byte check),
online submit → order **code** at submission → `PENDING_VERIFICATION` with SLA; verification queue (SLA
countdown, overdue highlight) and verify screen (image viewer with page tabs, zoom, rotate; edit tests;
confirm / clarify / reject) with SMS on every outcome; patient clarification reply (note + extra photos);
help-desk walk-in (find/register → tests while viewing the paper prescription, optional webcam photo →
inline verification → `AWAITING_PAYMENT`); fee categories and waiver request/approval (WAIVER payment;
fully waived → PAID); 3-part A4 slip PDF (WeasyPrint, Bangla + English, QR on the patient copy, Code128 on
bank + hospital copies, amount in words in both languages, prep text, reprints watermarked and audited);
order list/detail screens; PWA booking flow, order status timeline, test review with prices and
preparation, offline copy of the last orders (QR visible offline).

| Acceptance | Evidence |
|---|---|
| E2E online: submit → staff verify → patient sees price and prep text | `e2e/tests/online.spec.ts`; `test_online_submit_verify_patient_sees_price_and_prep` |
| E2E help desk: walk-in → slip has 3 parts with the same code; barcode decodes to it | `e2e/tests/walkin.spec.ts`; `tests/pdf/test_slip.py` (decodes each third of the page with zbar) |
| Price is snapshotted | `test_price_is_snapshotted` |

Also tested: clarification round trip, rejection, prescription rules, waiver (full, partial, self-approval
blocked, decided once), cancel rules, permissions, SLA overdue flag, SMS template length (≤ 2 segments,
bn + en), amount in words.

`tests/pdf/*` need Pango/zbar: they run in the API Docker image (`docker compose run --rm api pytest
tests/pdf`) and in CI; on a bare Windows host they are skipped.

## Deviations (with reasons)

- **Caddy instead of nginx** as the front door — automatic TLS, one fewer moving part ([ADR 0004](adr/0004-deployment.md)).
- **RustFS instead of the MinIO image** — S3-compatible, MinIO images unavailable ([ADR 0003](adr/0003-object-store.md)).
- **OTP sent synchronously, not via the outbox**; dev/test responses include the code when SMS is mocked ([ADR 0001](adr/0001-otp-delivery-and-dev-codes.md)).
- **Help-desk patients are not auto-linked to app accounts** by mobile ([ADR 0002](adr/0002-help-desk-patients-and-accounts.md)).
- **Waivers are a discount entered by the approver** on GENERAL prices ([ADR 0005](adr/0005-waivers.md)).
- **Prescription status mirrors the order** (DRAFT → SUBMITTED → VERIFIED / NEEDS_CLARIFICATION / REJECTED),
  both through `transition()`; the verification SLA lives on the order (and is copied to the prescription).
- **"My Appointments"** lists the patient's requests until slot booking exists (M5). **"My Reports"** is an
  empty state until M8.
- **Unpaid-order expiry job** is deferred to M4 (it belongs with payments), as the roadmap lists it there.
- `parameters.csv` is **intentionally empty**: reference ranges are clinical content (needed from M7).

## Open questions / items for BMU [BMU]

1. Confirmed catalog: tests, aliases, departments, containers, fasting rules, preparation text, TATs and
   prices — replaces `backend/seed/*.csv` (all PLACEHOLDER).
2. SMS provider (BTRC-registered sender ID) — production OTP login depends on it.
3. Account head printed on the bank copy (`SLIP_ACCOUNT_HEAD`), and whether the bank prints a receipt number.
4. Is a prescription mandatory for every test? (`requires_prescription` per test; BG is placeholder-false.)
5. Who may approve waivers, and are there fixed staff/concession prices instead of a discount per case?
6. Verification SLA (default 4 h) and order expiry (default 7 days).
7. Should a help-desk patient be claimable by an app account later, and with what identity check?
8. Hosting (on-prem vs Bangladeshi data centre), domain, data retention — needed before go-live.
9. Analyzer barcode length limits and label/receipt printer models (M6).

## Next: M4 — Payments

Payment service + adapter interface + mock gateway page, SSLCommerz sandbox, bank teller screen
(`/teller` is reserved in navigation), counter cash, refunds, unpaid-order expiry, reconciliation.
