from __future__ import annotations

import uuid
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, Response, UploadFile
from sqlalchemy import select

from app.core import audit, clock, settings_store
from app.core.actor import Actor
from app.core.errors import Forbidden, Invalid, NotFound
from app.deps import DB, require
from app.modules.documents import token as token_doc
from app.modules.identity import service as identity
from app.modules.orders import service as orders
from app.modules.orders.models import LabOrder
from app.modules.patients import service as patients
from app.modules.payments import reconciliation, refunds, schemas, service
from app.modules.payments.models import (
    BankColumnMapping,
    BankStatementImport,
    BankStatementLine,
    Payment,
    PaymentMethod,
    Refund,
    RefundStatus,
)
from app.modules.queue.models import QueueToken

router = APIRouter(prefix="/staff", tags=["staff-payments"])

Receive = Annotated[Actor, Depends(require("payment.teller.receive", "payment.counter.receive"))]
Look = Annotated[Actor, Depends(require("payment.teller.receive", "payment.counter.receive", "payment.view"))]
Viewer = Annotated[Actor, Depends(require("payment.view"))]


def _token_out(t: QueueToken | None) -> schemas.TokenOut | None:
    return schemas.TokenOut.model_validate(t) if t else None


def _lookup_out(db: DB, lk: service.Lookup) -> schemas.LookupOut:
    o = lk.order
    patient = patients.get(db, o.patient_id)
    paid = (
        schemas.PaidInfo(paid_at=lk.paid_payment.paid_at, method=lk.paid_payment.method, amount=lk.paid_payment.amount)
        if lk.paid_payment
        else None
    )
    return schemas.LookupOut(
        order_id=o.id,
        order_code=o.order_code or "",
        state=lk.state,
        status=o.status,
        priority=o.priority,
        patient_name=patient.full_name,
        patient_age=patient.age,
        tests=[i.abbreviation for i in o.active_items],
        subtotal=o.subtotal,
        discount=o.discount,
        total=o.total,
        amount_due=lk.amount_due,
        paid=paid,
        token=_token_out(lk.token),
        receipt_no_required=settings_store.get_bool(db, "teller_require_receipt_no"),
        counter_enabled=settings_store.get_bool(db, "counter_payment_enabled"),
    )


@router.get("/payments/lookup/{ref}", response_model=schemas.LookupOut)
def lookup(ref: str, db: DB, actor: Look) -> schemas.LookupOut:
    """Scan or type the code (any format). Shows name, code and amount, or a clear ALREADY_PAID /
    NOT_VERIFIED / EXPIRED state."""
    lk = service.lookup(db, ref)
    service.audit_view(db, actor, lk.order)
    db.commit()
    return _lookup_out(db, lk)


@router.post("/payments/receive/{ref}", response_model=schemas.ReceiptOut)
def receive(ref: str, data: schemas.ReceiveIn, db: DB, actor: Receive) -> schemas.ReceiptOut:
    method = PaymentMethod(data.method)
    needed = "payment.teller.receive" if method == PaymentMethod.BANK_TELLER else "payment.counter.receive"
    if not actor.can(needed):
        raise Forbidden("MISSING_PERMISSION", permission=needed)
    r = service.receive_in_person(db, ref, method, actor, data.receipt_no)
    db.commit()
    patient = patients.get(db, r.order.patient_id)
    return schemas.ReceiptOut(
        payment_id=r.payment.id,
        order_code=r.order.order_code or "",
        patient_name=patient.full_name,
        amount=r.payment.amount,
        method=r.payment.method,
        paid_at=r.payment.paid_at or clock.now(),
        receipt_no=r.payment.bank_receipt_no,
        token=schemas.TokenOut.model_validate(r.token),
    )


@router.post("/tokens/{token_id}/print", response_class=Response, responses={200: {"content": {"application/pdf": {}}}})
def print_token(
    token_id: uuid.UUID, db: DB, actor: Annotated[Actor, Depends(require("queue.token.print"))]
) -> Response:
    token = db.get(QueueToken, token_id)
    if token is None:
        raise NotFound("token")
    order = db.get(LabOrder, token.order_id)
    assert order is not None
    pdf = token_doc.render_token(db, token, order)
    audit.record(
        db,
        actor,
        "token.print",
        entity_type="queue_token",
        entity_id=token.id,
        patient_id=order.patient_id,
        after={"label": token.label},
    )
    db.commit()
    return Response(content=pdf, media_type="application/pdf", headers={"Cache-Control": "no-store"})


@router.get("/payments/day-close", response_model=schemas.DayCloseOut)
def day_close(
    db: DB,
    actor: Look,
    day: date | None = None,
    staff_id: uuid.UUID | None = None,
) -> schemas.DayCloseOut:
    """Count and total per teller for a business day (Asia/Dhaka). Tellers see their own; `payment.view`
    holders can look at anyone's."""
    target = staff_id or actor.id
    if target is None:
        raise Invalid("STAFF_REQUIRED")
    if target != actor.id and not actor.can("payment.view"):
        raise Forbidden("MISSING_PERMISSION", permission="payment.view")
    dc = service.day_close(db, target, day or clock.today())
    rows = []
    for p in dc.rows:
        code = db.scalar(select(LabOrder.order_code).where(LabOrder.id == p.order_id))
        tok = db.scalar(
            select(QueueToken).where(QueueToken.order_id == p.order_id).order_by(QueueToken.created_at).limit(1)
        )
        rows.append(
            schemas.DayCloseRow(
                payment_id=p.id,
                order_code=code,
                paid_at=p.paid_at,
                amount=p.amount,
                method=p.method,
                status=p.status,
                receipt_no=p.bank_receipt_no,
                token=tok.label if tok else None,
            )
        )
    stations = {p.station for p in dc.rows if p.station}
    return schemas.DayCloseOut(
        day=dc.day,
        staff_id=target,
        staff_name=identity.staff_name(db, target) or "",
        station=", ".join(sorted(stations)) or None,
        count=dc.count,
        total=dc.total,
        refunded_total=dc.refunded_total,
        net=dc.total - dc.refunded_total,
        rows=rows,
    )


# ---- payments of an order, refunds ---------------------------------------------------------------


@router.get("/payments/by-order/{ref}", response_model=schemas.OrderPayments)
def by_order(ref: str, db: DB, _: Annotated[Actor, Depends(require("payment.view"))]) -> schemas.OrderPayments:
    order = orders.get_by_ref(db, ref)
    pays = service.for_order(db, order.id)
    rfs = [r for p in pays for r in service.refund_for(db, p.id)]
    return schemas.OrderPayments(
        order_id=order.id,
        order_code=order.order_code or "",
        patient_name=patients.get(db, order.patient_id).full_name,
        total=order.total,
        payments=[schemas.PaymentOut.model_validate(p) for p in pays],
        refunds=[schemas.RefundOut.model_validate(r) for r in rfs],
    )


@router.post("/payments/{payment_id}/refund", response_model=schemas.RefundOut, status_code=201)
def request_refund(
    payment_id: uuid.UUID,
    data: schemas.RefundRequestIn,
    db: DB,
    actor: Annotated[Actor, Depends(require("payment.refund.request"))],
) -> Refund:
    r = refunds.request(db, payment_id, data.reason, actor)
    db.commit()
    return r


@router.get("/refunds", response_model=list[schemas.RefundRow])
def list_refunds(
    db: DB,
    _: Annotated[Actor, Depends(require("payment.refund.request", "payment.refund.approve", "payment.view"))],
    status: RefundStatus = RefundStatus.REQUESTED,
) -> list[schemas.RefundRow]:
    rows = []
    for r in service.open_refunds(db, status):
        order = db.get(LabOrder, r.order_id)
        pay = db.get(Payment, r.payment_id)
        assert order is not None and pay is not None
        rows.append(
            schemas.RefundRow(
                **schemas.RefundOut.model_validate(r).model_dump(),
                order_code=order.order_code,
                patient_name=patients.get(db, order.patient_id).full_name,
                payment_method=pay.method,
                provider=pay.provider,
            )
        )
    return rows


@router.post("/refunds/{refund_id}/approve", response_model=schemas.RefundOut)
def approve_refund(
    refund_id: uuid.UUID,
    data: schemas.RefundApproveIn,
    db: DB,
    actor: Annotated[Actor, Depends(require("payment.refund.approve"))],
) -> Refund:
    try:
        r = refunds.approve(db, refund_id, actor, data.mode, data.manual_reference)
    finally:
        db.commit()  # keep a FAILED provider call on record so it can be retried
    return r


@router.post("/refunds/{refund_id}/reject", response_model=schemas.RefundOut)
def reject_refund(
    refund_id: uuid.UUID,
    data: schemas.RefundRejectIn,
    db: DB,
    actor: Annotated[Actor, Depends(require("payment.refund.approve"))],
) -> Refund:
    r = refunds.reject(db, refund_id, actor, data.reason)
    db.commit()
    return r


# ---- reconciliation -------------------------------------------------------------------------------

Reconcile = Annotated[Actor, Depends(require("payment.reconcile"))]


@router.get("/reconciliation/mappings", response_model=list[schemas.MappingOut])
def mappings(db: DB, _: Reconcile) -> list[BankColumnMapping]:
    return list(db.scalars(select(BankColumnMapping).order_by(BankColumnMapping.bank_name)))


@router.get("/reconciliation/imports", response_model=list[schemas.ImportOut])
def imports(db: DB, _: Reconcile) -> list[BankStatementImport]:
    return list(db.scalars(select(BankStatementImport).order_by(BankStatementImport.created_at.desc()).limit(50)))


@router.post("/reconciliation/import", response_model=schemas.ImportOut)
def import_statement(
    db: DB,
    actor: Reconcile,
    file: Annotated[UploadFile, File()],
    bank_name: Annotated[str, Form(min_length=2, max_length=80)],
    date_column: Annotated[str, Form(min_length=1, max_length=80)],
    amount_column: Annotated[str, Form(min_length=1, max_length=80)],
    reference_column: Annotated[str, Form(min_length=1, max_length=80)],
    receipt_column: Annotated[str | None, Form(max_length=80)] = None,
    date_format: Annotated[str, Form(max_length=20)] = "%d/%m/%Y",
) -> BankStatementImport:
    raw = file.file.read(5_000_001)
    if len(raw) > 5_000_000:
        raise Invalid("FILE_TOO_LARGE", max_bytes=5_000_000)
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise Invalid("CSV_NOT_UTF8") from exc
    mapping = reconciliation.save_mapping(
        db, bank_name.strip(), date_column, amount_column, reference_column, receipt_column, date_format
    )
    imp = reconciliation.import_statement(db, text, file.filename or "statement.csv", mapping, actor)
    db.commit()
    return imp


@router.get("/reconciliation/exceptions", response_model=list[schemas.LineOut])
def exception_lines(db: DB, _: Reconcile) -> list[BankStatementLine]:
    return reconciliation.exceptions(db)


@router.post("/reconciliation/lines/{line_id}/resolve", response_model=schemas.LineOut)
def resolve_line(line_id: uuid.UUID, data: schemas.ResolveIn, db: DB, actor: Reconcile) -> BankStatementLine:
    line = reconciliation.resolve(db, line_id, data.note, actor)
    db.commit()
    return line
