"""FastAPI dependencies: DB session, staff/patient/device authentication, permission checks."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, Header, Query, Request
from sqlalchemy.orm import Session

from app.core.actor import Actor
from app.core.errors import Forbidden, Unauthorized
from app.db import get_db
from app.modules.identity import patient_auth
from app.modules.identity import service as identity
from app.modules.identity.models import Device, DeviceKind
from app.modules.patients.models import Account

DB = Annotated[Session, Depends(get_db)]


def client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


def _bearer(authorization: str | None) -> str:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise Unauthorized()
    return authorization.split(" ", 1)[1].strip()


def staff_context(
    db: DB, request: Request, authorization: Annotated[str | None, Header()] = None
) -> identity.StaffContext:
    ctx = identity.authenticate(db, _bearer(authorization))
    request.state.actor = ctx.actor
    return ctx


def staff_context_allow_locked(db: DB, authorization: Annotated[str | None, Header()] = None) -> identity.StaffContext:
    return identity.authenticate(db, _bearer(authorization), allow_locked=True)


StaffCtx = Annotated[identity.StaffContext, Depends(staff_context)]


def require(*permissions: str) -> Callable[..., Actor]:
    """Dependency factory: `actor: Actor = Depends(require("order.verify"))` — any listed permission."""

    def dep(ctx: StaffCtx) -> Actor:
        if ctx.staff.must_change_password:
            raise Forbidden("PASSWORD_CHANGE_REQUIRED")
        if not any(ctx.actor.can(p) for p in permissions):
            raise Forbidden("MISSING_PERMISSION", permission=permissions[0])
        return ctx.actor

    return dep


@dataclass(frozen=True)
class PatientContext:
    account: Account
    actor: Actor


def patient_context(db: DB, request: Request, authorization: Annotated[str | None, Header()] = None) -> PatientContext:
    account = patient_auth.authenticate(db, _bearer(authorization))
    actor = Actor(type="patient", id=account.id, label=f"account:{str(account.id)[:8]}")
    request.state.actor = actor
    return PatientContext(account=account, actor=actor)


PatientCtx = Annotated[PatientContext, Depends(patient_context)]


def device(*kinds: DeviceKind) -> Callable[..., Device]:
    def dep(
        db: DB,
        device_token: Annotated[str | None, Query(alias="device")] = None,
        x_device_token: Annotated[str | None, Header()] = None,
    ) -> Device:
        token = x_device_token or device_token
        if not token:
            raise Unauthorized("DEVICE_UNAUTHORIZED")
        return identity.authenticate_device(db, token, set(kinds))

    return dep
