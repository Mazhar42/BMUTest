from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, File, UploadFile

from app.deps import DB, PatientCtx
from app.modules.orders import schemas, service
from app.modules.prescriptions.router_common import read_images

router = APIRouter(prefix="/patient/orders", tags=["patient-orders"])


@router.post("", response_model=schemas.OrderOut, status_code=201)
def submit(data: schemas.SubmitOrderIn, db: DB, ctx: PatientCtx) -> schemas.OrderOut:
    order = service.submit_online(db, ctx.account, data, ctx.actor)
    db.commit()
    return service.to_out(db, order)


@router.get("", response_model=list[schemas.OrderOut])
def list_orders(db: DB, ctx: PatientCtx) -> list[schemas.OrderOut]:
    return [service.to_out(db, o) for o in service.list_for_account(db, ctx.account)]


@router.get("/{ref}", response_model=schemas.OrderOut)
def get_order(ref: str, db: DB, ctx: PatientCtx) -> schemas.OrderOut:
    """The order id, or its code in any format (SMS links carry the code)."""
    return service.to_out(db, service.get_for_account(db, ctx.account, ref))


@router.post("/{order_id}/clarification", response_model=schemas.OrderOut)
def respond(order_id: uuid.UUID, data: schemas.ClarificationResponseIn, db: DB, ctx: PatientCtx) -> schemas.OrderOut:
    order = service.respond_to_clarification(db, ctx.account, order_id, data, ctx.actor)
    db.commit()
    return service.to_out(db, order)


@router.post("/{order_id}/prescription-images", response_model=schemas.OrderOut)
def add_images(
    order_id: uuid.UUID, db: DB, ctx: PatientCtx, files: Annotated[list[UploadFile], File()]
) -> schemas.OrderOut:
    order = service.add_prescription_images(db, ctx.account, order_id, read_images(files), ctx.actor)
    db.commit()
    return service.to_out(db, order)


@router.post("/{order_id}/cancel", response_model=schemas.OrderOut)
def cancel(order_id: uuid.UUID, db: DB, ctx: PatientCtx) -> schemas.OrderOut:
    order = service.cancel_by_patient(db, ctx.account, order_id, ctx.actor)
    db.commit()
    return service.to_out(db, order)
