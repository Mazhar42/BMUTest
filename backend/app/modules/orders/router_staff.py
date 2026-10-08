from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response

from app.core import audit
from app.core.actor import Actor
from app.deps import DB, require
from app.modules.orders import schemas, service
from app.modules.orders.models import OrderStatus, WaiverRequest, WaiverStatus

router = APIRouter(prefix="/staff", tags=["staff-orders"])

View = Annotated[Actor, Depends(require("order.view", "order.lookup", "order.verify"))]
Verify = Annotated[Actor, Depends(require("order.verify"))]


@router.get("/orders", response_model=schemas.OrderPage)
def list_orders(
    db: DB,
    _: View,
    status: OrderStatus | None = None,
    q: Annotated[str | None, Query(max_length=80)] = None,
    cursor: str | None = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> schemas.OrderPage:
    rows, nxt = service.list_orders(db, status, q, cursor, limit)
    return schemas.OrderPage(items=service.to_rows(db, rows), next_cursor=nxt)


@router.get("/orders/stats", response_model=dict[str, int])
def stats(db: DB, _: View) -> dict[str, int]:
    return {**service.counts_by_status(db), "OVERDUE_VERIFICATION": service.overdue_count(db)}


@router.get("/orders/{ref}", response_model=schemas.StaffOrderOut)
def get_order(ref: str, db: DB, actor: View) -> schemas.StaffOrderOut:
    """The order id, or its code in any format (typed or scanned)."""
    order = service.get_by_ref(db, ref)
    audit.record(db, actor, "order.view", entity_type="lab_order", entity_id=order.id, patient_id=order.patient_id)
    db.commit()
    return service.to_staff_out(db, order)


@router.get("/patients/{patient_id}/orders", response_model=list[schemas.OrderRow])
def patient_orders(
    patient_id: uuid.UUID, db: DB, _: Annotated[Actor, Depends(require("patient.view", "order.view"))]
) -> list[schemas.OrderRow]:
    return service.to_rows(db, service.search_patient_orders(db, patient_id))


# ---- verification queue ----------------------------------------------------------------------------


@router.get("/verification/queue", response_model=list[schemas.OrderRow])
def queue(db: DB, _: Verify, status: OrderStatus = OrderStatus.PENDING_VERIFICATION) -> list[schemas.OrderRow]:
    return service.to_rows(db, service.verification_queue(db, status))


@router.post("/orders/{order_id}/verify", response_model=schemas.StaffOrderOut)
def verify(order_id: uuid.UUID, data: schemas.VerifyIn, db: DB, actor: Verify) -> schemas.StaffOrderOut:
    order = service.verify_confirm(db, order_id, data, actor)
    db.commit()
    return service.to_staff_out(db, order)


@router.post("/orders/{order_id}/clarify", response_model=schemas.StaffOrderOut)
def clarify(order_id: uuid.UUID, data: schemas.ReasonIn, db: DB, actor: Verify) -> schemas.StaffOrderOut:
    order = service.request_clarification(db, order_id, data.reason, actor)
    db.commit()
    return service.to_staff_out(db, order)


@router.post("/orders/{order_id}/reject", response_model=schemas.StaffOrderOut)
def reject(order_id: uuid.UUID, data: schemas.ReasonIn, db: DB, actor: Verify) -> schemas.StaffOrderOut:
    order = service.reject(db, order_id, data.reason, actor)
    db.commit()
    return service.to_staff_out(db, order)


# ---- help desk -------------------------------------------------------------------------------------


@router.post("/orders/walkin", response_model=schemas.StaffOrderOut, status_code=201)
def walkin(
    data: schemas.WalkinIn, db: DB, actor: Annotated[Actor, Depends(require("order.create_walkin"))]
) -> schemas.StaffOrderOut:
    order = service.create_walkin(db, data, actor)
    db.commit()
    return service.to_staff_out(db, order)


@router.post("/orders/{order_id}/cancel", response_model=schemas.StaffOrderOut)
def cancel(
    order_id: uuid.UUID, data: schemas.ReasonIn, db: DB, actor: Annotated[Actor, Depends(require("order.cancel"))]
) -> schemas.StaffOrderOut:
    order = service.cancel(db, service.get_locked(db, order_id), actor, data.reason)
    db.commit()
    return service.to_staff_out(db, order)


@router.post(
    "/orders/{order_id}/slip",
    response_class=Response,
    responses={200: {"content": {"application/pdf": {}}}},
)
def slip(
    order_id: uuid.UUID,
    db: DB,
    actor: Annotated[Actor, Depends(require("order.reprint_slip", "order.create_walkin"))],
) -> Response:
    """Print the 3-part slip. The first print is the original; every later one is watermarked REPRINT n."""
    pdf = service.print_slip(db, order_id, actor)
    db.commit()
    return Response(content=pdf, media_type="application/pdf", headers={"Cache-Control": "no-store"})


# ---- waivers ---------------------------------------------------------------------------------------


@router.post("/orders/{order_id}/waivers", response_model=schemas.WaiverOut, status_code=201)
def request_waiver(
    order_id: uuid.UUID,
    data: schemas.WaiverRequestIn,
    db: DB,
    actor: Annotated[Actor, Depends(require("waiver.request"))],
) -> WaiverRequest:
    w = service.request_waiver(db, order_id, data, actor)
    db.commit()
    return w


@router.get("/waivers", response_model=list[schemas.WaiverQueueRow])
def waivers(
    db: DB,
    _: Annotated[Actor, Depends(require("waiver.approve", "waiver.request"))],
    status: WaiverStatus = WaiverStatus.REQUESTED,
) -> list[schemas.WaiverQueueRow]:
    rows = service.waiver_queue(db, status)
    orders = {w.order_id: service.get(db, w.order_id) for w in rows}
    order_rows = {r.id: r for r in service.to_rows(db, list(orders.values()))}
    return [
        schemas.WaiverQueueRow(
            waiver=schemas.WaiverOut.model_validate(w),
            order=order_rows[w.order_id],
            subtotal=orders[w.order_id].subtotal,
        )
        for w in rows
    ]


@router.post("/waivers/{waiver_id}/decision", response_model=schemas.WaiverOut)
def decide(
    waiver_id: uuid.UUID,
    data: schemas.WaiverDecisionIn,
    db: DB,
    actor: Annotated[Actor, Depends(require("waiver.approve"))],
) -> WaiverRequest:
    w = service.decide_waiver(db, waiver_id, data, actor)
    db.commit()
    return w
