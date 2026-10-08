# Windows equivalent of the Makefile:  ./make.ps1 up | migrate | seed | check | e2e | gen-api | web | down
param([Parameter(Position = 0)][string]$Target = "help")
$ErrorActionPreference = "Stop"
$Root = $PSScriptRoot
function Api([string]$cmd) { docker compose exec -T api sh -c $cmd; if ($LASTEXITCODE) { exit $LASTEXITCODE } }
function Run([scriptblock]$b) { & $b; if ($LASTEXITCODE) { exit $LASTEXITCODE } }

switch ($Target) {
  "up" {
    Run { docker compose up -d --build postgres redis minio api worker beat }
    Api "until curl -fs localhost:8000/api/v1/health >/dev/null; do sleep 1; done"
  }
  "down" { Run { docker compose down } }
  "migrate" { Api "alembic upgrade head" }
  "seed" { Api "python -m app.cli seed --demo" }
  "test" { Api "pytest" }
  "check-backend" { Api "ruff check app tests && ruff format --check app tests && mypy && pytest" }
  "check-frontend" {
    Push-Location "$Root/frontend"
    try { Run { pnpm install --frozen-lockfile }; Run { pnpm -r lint }; Run { pnpm -r typecheck }; Run { pnpm -r test } } finally { Pop-Location }
  }
  "check" { & $PSCommandPath check-backend; & $PSCommandPath check-frontend }
  "e2e" { Push-Location "$Root/e2e"; try { Run { pnpm install --frozen-lockfile }; Run { pnpm exec playwright test } } finally { Pop-Location } }
  "gen-api" {
    docker compose exec -T api python -m app.cli openapi | Out-File -Encoding utf8NoBOM "$Root/frontend/packages/api-client/openapi.json"
    Push-Location "$Root/frontend"; try { Run { pnpm --filter @bmu/api-client gen } } finally { Pop-Location }
  }
  "web" { Push-Location "$Root/frontend"; try { pnpm dev } finally { Pop-Location } }
  "logs" { docker compose logs -f api worker beat }
  "superadmin" { docker compose exec api python -m app.cli create-superadmin }
  "backup" { Api "python -m app.cli backup" }
  "up-prod" { Run { docker compose --profile prod up -d --build } }
  default { Write-Host "targets: up down migrate seed check check-backend check-frontend test e2e gen-api web logs superadmin backup up-prod" }
}
