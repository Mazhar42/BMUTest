from __future__ import annotations

import uuid

from fastapi import APIRouter

from app.core.errors import NotFound
from app.deps import DB, PatientCtx
from app.modules.orders import service as orders
from app.modules.orders.models import LabOrder
from app.modules.payments import schemas as pay_schemas
from app.modules.payments import service
from app.modules.payments.models import PaymentStatus

router = APIRouter(prefix="/patient", tags=["patient-payments"])


@router.post("/orders/{order_id}/pay", response_model=pay_schemas.PayOut)
def pay(order_id: uuid.UUID, data: pay_schemas.PayIn, db: DB, ctx: PatientCtx) -> pay_schemas.PayOut:
    """Start an online payment for the amount due; the app redirects the patient to `redirect_url`."""
    order = orders.get_for_account(db, ctx.account, str(order_id))
    payment = service.start_online_payment(db, order, data.method, ctx.actor)
    db.commit()
    return pay_schemas.PayOut(
        payment_id=payment.id,
        tran_id=payment.gateway_tran_id or "",
        redirect_url=payment.redirect_url or "",
        amount=payment.amount,
    )


@router.get("/payments/{tran_id}", response_model=pay_schemas.PaymentStatusOut)
def status(tran_id: str, db: DB, ctx: PatientCtx) -> pay_schemas.PaymentStatusOut:
    """Polled by the result page. A payment that is still PENDING is re-checked with the gateway, so the
    patient sees the outcome even if the IPN could not reach us."""
    payment = service.by_tran_id(db, tran_id)
    order = db.get(LabOrder, payment.order_id)
    if order is None or order.account_id != ctx.account.id:
        raise NotFound("payment")
    if payment.status == PaymentStatus.PENDING:
        payment = service.requery(db, payment.id)
        db.commit()
        order = db.get(LabOrder, payment.order_id)
        assert order is not None
    return pay_schemas.PaymentStatusOut(
        tran_id=tran_id,
        status=payment.status,
        reason=payment.status_reason,
        amount=payment.amount,
        order_id=order.id,
        order_code=order.order_code,
        order_status=order.status,
    )
