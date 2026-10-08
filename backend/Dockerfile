# syntax=docker/dockerfile:1.7
FROM python:3.12-slim-bookworm AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    PATH="/opt/venv/bin:$PATH" \
    TZ=UTC

# WeasyPrint needs Pango/HarfBuzz (correct Bengali shaping). Noto Sans + Noto Sans Bengali are bundled.
# libzbar0 decodes barcodes in tests; postgresql-client provides pg_dump for backups.
RUN apt-get update && apt-get install -y --no-install-recommends \
        libpango-1.0-0 libpangoft2-1.0-0 libharfbuzz0b libharfbuzz-subset0 libfontconfig1 \
        fonts-noto-core fonts-noto-ui-core shared-mime-info \
        libzbar0 postgresql-client curl ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && fc-cache -f

COPY --from=ghcr.io/astral-sh/uv:0.9 /uv /usr/local/bin/uv

WORKDIR /app
# Dev image (docker-compose.yml) keeps the test/lint tools; the production image passes UV_SYNC_ARGS=--no-dev.
ARG UV_SYNC_ARGS=""
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv uv sync --frozen --no-install-project $UV_SYNC_ARGS

COPY . .

RUN useradd --create-home --uid 1000 bmu && mkdir -p /data/storage && chown -R bmu /data /app
USER bmu

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*"]
