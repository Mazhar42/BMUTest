# BMU Lab task runner. Windows without make: ./make.ps1 <target>
COMPOSE ?= docker compose
API ?= $(COMPOSE) exec -T api
CORE = postgres redis minio api worker beat

.PHONY: up down migrate seed check check-backend check-frontend test e2e gen-api web logs shell psql \
        superadmin backup restore-drill up-prod load-test audit-deps

up:
	$(COMPOSE) up -d --build $(CORE)
	$(COMPOSE) exec -T api sh -c 'until curl -fs localhost:8000/api/v1/health >/dev/null; do sleep 1; done'

down:
	$(COMPOSE) down

migrate:
	$(API) alembic upgrade head

seed:
	$(API) python -m app.cli seed --demo

check: check-backend check-frontend

check-backend:
	$(API) ruff check app tests
	$(API) ruff format --check app tests
	$(API) mypy
	$(API) pytest

test:
	$(API) pytest

check-frontend:
	cd frontend && pnpm install --frozen-lockfile && pnpm -r lint && pnpm -r typecheck && pnpm -r test

e2e:
	cd e2e && pnpm install --frozen-lockfile && pnpm exec playwright test

gen-api:
	$(API) python -m app.cli openapi > frontend/packages/api-client/openapi.json
	cd frontend && pnpm --filter @bmu/api-client gen

web:
	cd frontend && pnpm dev

logs:
	$(COMPOSE) logs -f api worker beat

shell:
	$(COMPOSE) exec api bash

psql:
	$(COMPOSE) exec postgres psql -U bmu bmu

superadmin:
	$(COMPOSE) exec api python -m app.cli create-superadmin

backup:
	$(COMPOSE) exec -T api python -m app.cli backup

restore-drill:
	sh ops/restore-drill.sh

up-prod:
	$(COMPOSE) --profile prod up -d --build

load-test:
	docker run --rm -i --network host -v $(PWD)/ops/load:/scripts grafana/k6 run /scripts/morning-peak.js

audit-deps:
	$(API) pip-audit
	cd frontend && pnpm audit --prod
