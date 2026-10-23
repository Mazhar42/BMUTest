"""FastAPI application: /api/v1/{patient,staff,public}/* (ROADMAP §6.3)."""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable

from fastapi import APIRouter, FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app import models_registry  # noqa: F401  (register all mappers)
from app.config import get_settings
from app.core import logging as bmu_logging
from app.core.actor import set_request_meta
from app.core.errors import install_handlers
from app.deps import DB
from app.modules.catalog.router_patient import router as catalog_patient
from app.modules.catalog.router_staff import router as catalog_staff
from app.modules.identity.router_patient import router as identity_patient
from app.modules.identity.router_staff import router as identity_staff
from app.modules.orders.router_patient import router as orders_patient
from app.modules.orders.router_staff import router as orders_staff
from app.modules.patients.router_patient import router as patients_patient
from app.modules.patients.router_staff import router as patients_staff
from app.modules.payments.router_patient import router as payments_patient
from app.modules.payments.router_public import router as payments_public
from app.modules.payments.router_staff import router as payments_staff
from app.modules.prescriptions.router_patient import router as prescriptions_patient
from app.modules.prescriptions.router_staff import router as prescriptions_staff

log = logging.getLogger("bmu")

VERSION = "0.1.0"


def create_app() -> FastAPI:
    settings = get_settings()
    bmu_logging.configure(settings.log_level)
    app = FastAPI(
        title="BMU Lab API",
        version=VERSION,
        docs_url="/api/docs",
        redoc_url=None,
        openapi_url="/api/openapi.json",
    )
    install_handlers(app)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def request_context(request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        set_request_meta(request.client.host if request.client else None, request.headers.get("user-agent"))
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault("X-Frame-Options", "DENY")
        if request.url.path.startswith("/api/v1/"):
            response.headers.setdefault("Cache-Control", "no-store")
        return response

    api = APIRouter(prefix="/api/v1")

    @api.get("/health", tags=["ops"])
    def health(db: DB) -> dict[str, str]:
        db.execute(text("SELECT 1"))
        return {"status": "ok", "version": VERSION, "env": settings.env}

    for router in (
        identity_staff,
        identity_patient,
        catalog_staff,
        catalog_patient,
        patients_staff,
        patients_patient,
        prescriptions_staff,
        prescriptions_patient,
        orders_staff,
        orders_patient,
        payments_staff,
        payments_patient,
        payments_public,
    ):
        api.include_router(router)
    app.include_router(api)
    return app


app = create_app()
