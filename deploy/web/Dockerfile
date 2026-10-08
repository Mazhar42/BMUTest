# syntax=docker/dockerfile:1.7
# Front door: builds the patient PWA (/) and the staff app (/staff/), serves them with Caddy, proxies /api
# to the API container and obtains/renews the TLS certificate automatically (docs/adr/0004).
FROM node:22-alpine AS build
RUN corepack enable
WORKDIR /src
COPY frontend/package.json frontend/pnpm-lock.yaml frontend/pnpm-workspace.yaml ./
COPY frontend/apps/patient/package.json apps/patient/
COPY frontend/apps/staff/package.json apps/staff/
COPY frontend/packages/ui/package.json packages/ui/
COPY frontend/packages/i18n/package.json packages/i18n/
COPY frontend/packages/api-client/package.json packages/api-client/
RUN --mount=type=cache,target=/root/.local/share/pnpm/store pnpm install --frozen-lockfile
COPY frontend/ ./
RUN pnpm --filter @bmu/patient build && pnpm --filter @bmu/staff build

FROM caddy:2-alpine
COPY deploy/web/Caddyfile /etc/caddy/Caddyfile
COPY --from=build /src/apps/patient/dist /srv/patient
COPY --from=build /src/apps/staff/dist /srv/staff
