from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select

from app.core import audit
from app.core.actor import Actor
from app.core.errors import NotFound
from app.deps import DB, StaffCtx, client_ip, require, staff_context_allow_locked
from app.modules.identity import schemas, service
from app.modules.identity.models import Device, Staff

router = APIRouter(prefix="/staff", tags=["staff-auth"])


@router.post("/auth/login", response_model=schemas.LoginOut)
def login(data: schemas.LoginIn, db: DB, request: Request) -> schemas.LoginOut:
    try:
        return service.login(db, data, client_ip(request), request.headers.get("user-agent"))
    finally:
        db.commit()  # persist failed-login counters and audit rows even on error


@router.post("/auth/totp", response_model=schemas.LoginOut)
def login_totp(data: schemas.TotpIn, db: DB, request: Request) -> schemas.LoginOut:
    try:
        return service.login_totp(db, data, client_ip(request), request.headers.get("user-agent"))
    finally:
        db.commit()


@router.get("/auth/me", response_model=schemas.StaffMe)
def get_me(ctx: StaffCtx) -> schemas.StaffMe:
    return service.me(ctx.staff, ctx.session)


@router.post("/auth/unlock", response_model=schemas.StaffMe)
def unlock(
    data: schemas.UnlockIn,
    db: DB,
    ctx: Annotated[service.StaffContext, Depends(staff_context_allow_locked)],
) -> schemas.StaffMe:
    try:
        service.unlock(db, ctx, data.secret)
    finally:
        db.commit()
    return service.me(ctx.staff, ctx.session)


@router.post("/auth/lock", status_code=204)
def lock(db: DB, ctx: StaffCtx) -> None:
    service.lock(db, ctx)
    db.commit()


@router.post("/auth/logout", status_code=204)
def logout(db: DB, ctx: Annotated[service.StaffContext, Depends(staff_context_allow_locked)]) -> None:
    service.logout(db, ctx)
    db.commit()


@router.patch("/auth/me/preferences", response_model=schemas.StaffMe)
def preferences(data: schemas.PreferencesIn, db: DB, ctx: StaffCtx) -> schemas.StaffMe:
    ctx.staff.preferred_language = data.preferred_language
    db.commit()
    return service.me(ctx.staff, ctx.session)


@router.post("/auth/me/pin", status_code=204)
def set_pin(data: schemas.PinIn, db: DB, ctx: StaffCtx) -> None:
    service.set_pin(db, ctx, data)
    db.commit()


@router.post("/auth/me/password", status_code=204)
def change_password(data: schemas.PasswordChangeIn, db: DB, ctx: StaffCtx) -> None:
    service.change_password(db, ctx, data)
    db.commit()


# ---- admin: staff ------------------------------------------------------------------------------


@router.get("/admin/staff", response_model=list[schemas.StaffOut])
def list_staff(db: DB, _: Annotated[Actor, Depends(require("staff.manage"))]) -> list[Staff]:
    return list(db.scalars(select(Staff).order_by(Staff.full_name)))


@router.post("/admin/staff", response_model=schemas.StaffOut, status_code=201)
def create_staff(data: schemas.StaffCreate, db: DB, actor: Annotated[Actor, Depends(require("staff.manage"))]) -> Staff:
    staff = service.create_staff(db, data, actor)
    db.commit()
    return staff


@router.patch("/admin/staff/{staff_id}", response_model=schemas.StaffOut)
def update_staff(
    staff_id: uuid.UUID,
    data: schemas.StaffUpdate,
    db: DB,
    actor: Annotated[Actor, Depends(require("staff.manage"))],
) -> Staff:
    staff = service.update_staff(db, staff_id, data, actor)
    db.commit()
    db.refresh(staff)
    return staff


@router.post("/admin/staff/{staff_id}/reset-totp", status_code=204)
def reset_totp(staff_id: uuid.UUID, db: DB, actor: Annotated[Actor, Depends(require("staff.manage"))]) -> None:
    service.reset_totp(db, staff_id, actor)
    db.commit()


@router.post("/admin/staff/{staff_id}/reset-password", status_code=204)
def reset_password(
    staff_id: uuid.UUID,
    data: schemas.PasswordResetIn,
    db: DB,
    actor: Annotated[Actor, Depends(require("staff.manage"))],
) -> None:
    service.reset_password(db, staff_id, data.new_password, actor)
    db.commit()


# ---- admin: devices (queue displays, kiosks, analyzers) ----------------------------------------


@router.get("/admin/devices", response_model=list[schemas.DeviceOut])
def list_devices(db: DB, _: Annotated[Actor, Depends(require("device.manage"))]) -> list[Device]:
    return list(db.scalars(select(Device).order_by(Device.created_at.desc())))


@router.post("/admin/devices", response_model=schemas.DeviceCreated, status_code=201)
def create_device(
    data: schemas.DeviceCreate, db: DB, actor: Annotated[Actor, Depends(require("device.manage"))]
) -> schemas.DeviceCreated:
    device, token = service.create_device(db, data, actor)
    db.commit()
    return schemas.DeviceCreated(**schemas.DeviceOut.model_validate(device).model_dump(), token=token)


@router.delete("/admin/devices/{device_id}", status_code=204)
def deactivate_device(device_id: uuid.UUID, db: DB, actor: Annotated[Actor, Depends(require("device.manage"))]) -> None:
    device = db.get(Device, device_id)
    if device is None:
        raise NotFound("device")
    device.is_active = False
    audit.record(db, actor, "device.deactivate", entity_type="device", entity_id=device.id)
    db.commit()
