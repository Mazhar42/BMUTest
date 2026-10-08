"""Error model: every API error is `{code, message_key, params}` (ROADMAP §6.3); the frontend translates."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from starlette.exceptions import HTTPException as StarletteHTTPException

log = logging.getLogger("bmu.errors")


class ErrorBody(BaseModel):
    code: str
    message_key: str
    params: dict[str, Any] = {}


class AppError(Exception):
    status_code = 400

    def __init__(
        self,
        code: str,
        message_key: str | None = None,
        params: dict[str, Any] | None = None,
        status_code: int | None = None,
    ) -> None:
        super().__init__(code)
        self.code = code
        self.message_key = message_key or f"errors.{code.lower()}"
        self.params = params or {}
        if status_code is not None:
            self.status_code = status_code

    def body(self) -> dict[str, Any]:
        return {"code": self.code, "message_key": self.message_key, "params": self.params}


class NotFound(AppError):
    status_code = 404

    def __init__(self, entity: str, **params: Any) -> None:
        super().__init__("NOT_FOUND", "errors.not_found", {"entity": entity, **params})


class Forbidden(AppError):
    status_code = 403

    def __init__(self, code: str = "FORBIDDEN", **params: Any) -> None:
        super().__init__(code, None, params)


class Unauthorized(AppError):
    status_code = 401

    def __init__(self, code: str = "UNAUTHORIZED", **params: Any) -> None:
        super().__init__(code, None, params)


class Conflict(AppError):
    status_code = 409

    def __init__(self, code: str, **params: Any) -> None:
        super().__init__(code, None, params)


class Invalid(AppError):
    status_code = 422

    def __init__(self, code: str, **params: Any) -> None:
        super().__init__(code, None, params)


class RateLimited(AppError):
    status_code = 429

    def __init__(self, code: str = "RATE_LIMITED", **params: Any) -> None:
        super().__init__(code, None, params)


class Gone(AppError):
    status_code = 410

    def __init__(self, code: str = "GONE", **params: Any) -> None:
        super().__init__(code, None, params)


def install_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app_error(_: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(status_code=exc.status_code, content=exc.body())

    @app.exception_handler(RequestValidationError)
    async def _validation(_: Request, exc: RequestValidationError) -> JSONResponse:
        fields = [
            {"loc": [str(p) for p in e.get("loc", [])], "type": e.get("type"), "msg": e.get("msg")}
            for e in exc.errors()
        ]
        return JSONResponse(
            status_code=422,
            content={"code": "VALIDATION_ERROR", "message_key": "errors.validation", "params": {"fields": fields}},
        )

    @app.exception_handler(StarletteHTTPException)
    async def _http(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        code = {404: "NOT_FOUND", 405: "METHOD_NOT_ALLOWED", 401: "UNAUTHORIZED", 403: "FORBIDDEN"}.get(
            exc.status_code, "HTTP_ERROR"
        )
        return JSONResponse(
            status_code=exc.status_code,
            content={"code": code, "message_key": f"errors.{code.lower()}", "params": {}},
        )

    @app.exception_handler(Exception)
    async def _unhandled(_: Request, exc: Exception) -> JSONResponse:
        log.exception("unhandled error", exc_info=exc)
        return JSONResponse(
            status_code=500,
            content={"code": "INTERNAL_ERROR", "message_key": "errors.internal", "params": {}},
        )
