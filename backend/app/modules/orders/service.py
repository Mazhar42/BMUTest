"""Lab orders (ROADMAP M3): online submission → verification queue (confirm / edit / clarify / reject),
help-desk walk-in orders with inline verification, fee-category waivers, slip printing."""

from __future__ import annotations

import uuid
from datetime import timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core import audit, clock, codes, settings_store
from app.core.actor import Actor
from app.core.errors import Conflict, Forbidden, Invalid, NotFound
from app.core.pagination import apply_cursor, page
from app.core.state_machine import can_transition, transition
from app.modules.catalog import service as catalog
from app.modules.catalog.models import FeeCategory, LabTest
from app.modules.orders import handlers as _handlers  # noqa: F401  (registers SMS handlers)
from app.modules.orders import schemas
from app.modules.orders.models import (
    ItemStatus,
    LabOrder,
    LabOrderItem,
    OrderStatus,
    WaiverRequest,
    WaiverStatus,
)
from app.modules.patients import service as patients
from app.modules.patients.models import Account, Channel, Patient
from app.modules.payments import service as payments
from app.modules.prescriptions import service as prescriptions
from app.modules.prescriptions.models import Prescription, PrescriptionStatus

CANCELLABLE = {
    OrderStatus.DRAFT,
    OrderStatus.PENDING_VERIFICATION,
    OrderStatus.NEEDS_CLARIFICATION,
    OrderStatus.AWAITING_PAYMENT,
}


# ---- helpers ---------------------------------------------------------------------------------------


def _tests(db: Session, test_ids: list[uuid.UUID]) -> list[LabTest]:
    unique = list(dict.fromkeys(test_ids))
    rows = {t.id: t for t in db.scalars(select(LabTest).where(LabTest.id.in_(unique)))}
    out: list[LabTest] = []
    for tid in unique:
        t = rows.get(tid)
        if t is None:
            raise Invalid("UNKNOWN_TEST", test_id=str(tid))
        if not t.active:
            raise Invalid("TEST_INACTIVE", test=t.code)
        out.append(t)
    return out


def _new_item(order: LabOrder, t: LabTest) -> LabOrderItem:
    price = catalog.current_price(t, FeeCategory.GENERAL)
    if price is None:
        raise Invalid("TEST_HAS_NO_PRICE", test=t.code)
    return LabOrderItem(
        id=uuid.uuid4(),
        order_id=order.id,
        test_id=t.id,
        department_id=t.department_id,
        test_code=t.code,
        test_name_en=t.name_en,
        test_name_bn=t.name_bn,
        abbreviation=t.abbreviation,
        price_snapshot=price,
        status=ItemStatus.ORDERED,
    )


def _recompute(order: LabOrder) -> None:
    order.subtotal = sum(i.price_snapshot for i in order.active_items)
    order.discount = min(order.discount or 0, order.subtotal)
    order.total = order.subtotal - order.discount


def _replace_items(db: Session, order: LabOrder, tests: list[LabTest], actor: Actor) -> dict[str, list[str]]:
    """Cancel removed tests (history kept), add new ones. Existing items keep their price snapshot."""
    wanted = {t.id: t for t in tests}
    current = {i.test_id: i for i in order.active_items}
    removed = [i for tid, i in current.items() if tid not in wanted]
    added = [t for tid, t in wanted.items() if tid not in current]
    for item in removed:
        transition(db, item, ItemStatus.CANCELLED, actor, reason="removed during verification")
    for t in added:
        order.items.append(_new_item(order, t))
    _recompute(order)
    return {"added": [t.code for t in added], "removed": [i.test_code for i in removed]}


def _check_prescription_rule(tests: list[LabTest], prescription: Prescription | None) -> None:
    if prescription is None and any(t.requires_prescription for t in tests):
        raise Invalid("PRESCRIPTION_REQUIRED", tests=[t.code for t in tests if t.requires_prescription])


def _assign_code(db: Session, order: LabOrder) -> None:
    order.order_code = codes.generate_order_code(db, clock.today())
    order.submitted_at = clock.now()


def _sla_due(db: Session) -> Any:
    return clock.now() + timedelta(hours=settings_store.get_int(db, "verification_sla_hours"))


def get(db: Session, order_id: uuid.UUID) -> LabOrder:
    o = db.get(LabOrder, order_id)
    if o is None:
        raise NotFound("order")
    return o


def get_locked(db: Session, order_id: uuid.UUID) -> LabOrder:
    o = db.get(LabOrder, order_id, with_for_update=True)
    if o is None:
        raise NotFound("order")
    return o


def by_code(db: Session, raw: str) -> LabOrder:
    code = codes.parse_order_code(raw)
    o = db.scalar(select(LabOrder).where(LabOrder.order_code == code))
    if o is None:
        raise NotFound("order", code=code)
    return o


def get_by_ref(db: Session, ref: str) -> LabOrder:
    """An order by UUID or by order code in any format."""
    try:
        return get(db, uuid.UUID(ref))
    except ValueError:
        return by_code(db, ref)


def patient_for_code(db: Session, raw: str) -> Patient | None:
    """Used by the staff patient search: a typed/scanned order code resolves to its patient."""
    try:
        code = codes.parse_order_code(raw)
    except codes.CodeMistyped:
        return None
    o = db.scalar(select(LabOrder).where(LabOrder.order_code == code))
    return patients.get(db, o.patient_id) if o else None


def _owned(db: Session, account: Account, order_id: uuid.UUID) -> LabOrder:
    o = db.get(LabOrder, order_id, with_for_update=True)
    if o is None or o.account_id != account.id:
        raise NotFound("order")
    return o


def _prescription(db: Session, order: LabOrder) -> Prescription | None:
    return db.get(Prescription, order.prescription_id) if order.prescription_id else None


def _move_prescription(db: Session, order: LabOrder, to: PrescriptionStatus, actor: Actor, reason: str | None) -> None:
    p = _prescription(db, order)
    if p is not None and can_transition(p, to):
        transition(db, p, to, actor, reason=reason)


# ---- online (patient) ------------------------------------------------------------------------------


def submit_online(db: Session, account: Account, data: schemas.SubmitOrderIn, actor: Actor) -> LabOrder:
    patient = patients.get_for_account(db, account.id, data.patient_id)
    prescription = None
    if data.prescription_id is not None:
        prescription = prescriptions.get(db, data.prescription_id)
        if prescription.patient_id != patient.id or prescription.status != PrescriptionStatus.DRAFT:
            raise Invalid("PRESCRIPTION_NOT_USABLE")
    tests = _tests(db, data.test_ids)
    _check_prescription_rule(tests, prescription)
    order = LabOrder(
        id=uuid.uuid4(),
        patient_id=patient.id,
        account_id=account.id,
        prescription_id=prescription.id if prescription else None,
        channel=Channel.APP,
        status=OrderStatus.DRAFT,
        lang=data.lang or account.preferred_language,
        notes=(data.notes or "").strip() or None,
        items=[],
    )
    db.add(order)
    for t in tests:
        order.items.append(_new_item(order, t))
    _recompute(order)
    _assign_code(db, order)
    order.sla_due_at = _sla_due(db)
    db.flush()
    transition(db, order, OrderStatus.PENDING_VERIFICATION, actor, data={"code": order.order_code})
    if prescription is not None:
        prescription.submitted_at = order.submitted_at
        prescription.sla_due_at = order.sla_due_at
        transition(db, prescription, PrescriptionStatus.SUBMITTED, actor)
    return order


def respond_to_clarification(
    db: Session, account: Account, order_id: uuid.UUID, data: schemas.ClarificationResponseIn, actor: Actor
) -> LabOrder:
    order = _owned(db, account, order_id)
    if order.status != OrderStatus.NEEDS_CLARIFICATION:
        raise Conflict("ORDER_NOT_AWAITING_CLARIFICATION")
    if data.test_ids is not None:
        tests = _tests(db, data.test_ids)
        _check_prescription_rule(tests, _prescription(db, order))
        _replace_items(db, order, tests, actor)
    if data.note:
        order.notes = data.note.strip()
    order.sla_due_at = _sla_due(db)
    transition(db, order, OrderStatus.PENDING_VERIFICATION, actor, reason=data.note)
    _move_prescription(db, order, PrescriptionStatus.SUBMITTED, actor, None)
    return order


def add_prescription_images(
    db: Session, account: Account, order_id: uuid.UUID, images: list[prescriptions.ImageIn], actor: Actor
) -> LabOrder:
    order = _owned(db, account, order_id)
    if order.status not in (OrderStatus.NEEDS_CLARIFICATION, OrderStatus.PENDING_VERIFICATION):
        raise Conflict("ORDER_LOCKED")
    p = _prescription(db, order)
    if p is None:
        p = prescriptions.create(db, order.patient_id, images, actor, order.channel)
        order.prescription_id = p.id
        db.flush()
        transition(db, p, PrescriptionStatus.SUBMITTED, actor)
    else:
        prescriptions.add_images(db, p, images, actor)
    return order


def cancel(db: Session, order: LabOrder, actor: Actor, reason: str) -> LabOrder:
    if order.status not in CANCELLABLE:
        raise Conflict("ORDER_NOT_CANCELLABLE", status=order.status.value)
    if payments.paid_amount(db, order.id, exclude_waiver=True) > 0:
        raise Conflict("ORDER_HAS_PAYMENT")
    transition(db, order, OrderStatus.CANCELLED, actor, reason=reason)
    return order


def cancel_by_patient(db: Session, account: Account, order_id: uuid.UUID, actor: Actor) -> LabOrder:
    return cancel(db, _owned(db, account, order_id), actor, "cancelled by patient")


def list_for_account(db: Session, account: Account, limit: int = 50) -> list[LabOrder]:
    return list(
        db.scalars(
            select(LabOrder)
            .where(LabOrder.account_id == account.id, LabOrder.status != OrderStatus.DRAFT)
            .order_by(LabOrder.created_at.desc())
            .limit(limit)
        )
    )


def get_for_account(db: Session, account: Account, ref: str) -> LabOrder:
    o = get_by_ref(db, ref)
    if o.account_id != account.id:
        raise NotFound("order")
    return o


# ---- verification (staff) --------------------------------------------------------------------------


def _pending(db: Session, order_id: uuid.UUID) -> LabOrder:
    order = get_locked(db, order_id)
    if order.status != OrderStatus.PENDING_VERIFICATION:
        raise Conflict("ORDER_NOT_PENDING_VERIFICATION", status=order.status.value)
    return order


def verify_confirm(db: Session, order_id: uuid.UUID, data: schemas.VerifyIn, actor: Actor) -> LabOrder:
    order = _pending(db, order_id)
    changes: dict[str, list[str]] = {"added": [], "removed": []}
    if data.test_ids is not None:
        changes = _replace_items(db, order, _tests(db, data.test_ids), actor)
    if not order.active_items:
        raise Invalid("ORDER_HAS_NO_TESTS")
    order.verified_at = clock.now()
    order.verified_by_staff_id = actor.id
    transition(db, order, OrderStatus.AWAITING_PAYMENT, actor, reason=data.note, data={"edits": changes})
    p = _prescription(db, order)
    if p is not None and can_transition(p, PrescriptionStatus.VERIFIED):
        p.verified_at = order.verified_at
        p.verified_by = actor.id
        transition(db, p, PrescriptionStatus.VERIFIED, actor)
    return order


def request_clarification(db: Session, order_id: uuid.UUID, note: str, actor: Actor) -> LabOrder:
    order = _pending(db, order_id)
    order.clarification_note = note.strip()
    transition(db, order, OrderStatus.NEEDS_CLARIFICATION, actor, reason=note)
    p = _prescription(db, order)
    if p is not None:
        p.clarification_note = order.clarification_note
    _move_prescription(db, order, PrescriptionStatus.NEEDS_CLARIFICATION, actor, note)
    return order


def reject(db: Session, order_id: uuid.UUID, reason: str, actor: Actor) -> LabOrder:
    order = get_locked(db, order_id)
    if order.status not in (OrderStatus.PENDING_VERIFICATION, OrderStatus.NEEDS_CLARIFICATION):
        raise Conflict("ORDER_NOT_PENDING_VERIFICATION", status=order.status.value)
    transition(db, order, OrderStatus.REJECTED, actor, reason=reason)
    _move_prescription(db, order, PrescriptionStatus.REJECTED, actor, reason)
    return order


def verification_queue(db: Session, status: OrderStatus, limit: int = 200) -> list[LabOrder]:
    return list(
        db.scalars(
            select(LabOrder)
            .where(LabOrder.status == status)
            .order_by(LabOrder.sla_due_at.asc().nulls_last(), LabOrder.submitted_at)
            .limit(limit)
        )
    )


# ---- help desk walk-in -----------------------------------------------------------------------------


def create_walkin(db: Session, data: schemas.WalkinIn, actor: Actor) -> LabOrder:
    patient = patients.get(db, data.patient_id)
    prescription = None
    if data.prescription_id is not None:
        prescription = prescriptions.get(db, data.prescription_id)
        if prescription.patient_id != patient.id or prescription.status != PrescriptionStatus.DRAFT:
            raise Invalid("PRESCRIPTION_NOT_USABLE")
    tests = _tests(db, data.test_ids)
    order = LabOrder(
        id=uuid.uuid4(),
        patient_id=patient.id,
        account_id=patient.account_id,
        prescription_id=prescription.id if prescription else None,
        channel=Channel.HELPDESK,
        status=OrderStatus.DRAFT,
        priority=data.priority,
        lang=data.lang,
        notes=(data.notes or "").strip() or None,
        created_by_staff_id=actor.id,
        items=[],
    )
    db.add(order)
    for t in tests:
        order.items.append(_new_item(order, t))
    _recompute(order)
    _assign_code(db, order)
    order.verified_at = order.submitted_at
    order.verified_by_staff_id = actor.id
    db.flush()
    # Inline verification: the help desk checked the paper prescription with the patient present.
    transition(db, order, OrderStatus.AWAITING_PAYMENT, actor, data={"code": order.order_code, "inline": True})
    if prescription is not None:
        prescription.verified_at = order.verified_at
        prescription.verified_by = actor.id
        transition(db, prescription, PrescriptionStatus.VERIFIED, actor)
    if data.fee_category != FeeCategory.GENERAL:
        _open_waiver(db, order, data.fee_category, data.waiver_reason or "", actor)
    return order


# ---- waivers (ROADMAP §5.4) ------------------------------------------------------------------------


def _open_waiver(db: Session, order: LabOrder, fee_category: FeeCategory, reason: str, actor: Actor) -> WaiverRequest:
    w = WaiverRequest(
        id=uuid.uuid4(),
        order_id=order.id,
        fee_category=fee_category,
        requested_by=actor.id or uuid.UUID(int=0),
        request_reason=reason.strip(),
        status=WaiverStatus.REQUESTED,
    )
    db.add(w)
    audit.record(
        db,
        actor,
        "waiver_request.REQUESTED",
        entity_type="waiver_request",
        entity_id=w.id,
        patient_id=order.patient_id,
        after={"order": order.order_code, "fee_category": fee_category.value},
        reason=reason,
    )
    return w


def waivers_for(db: Session, order_id: uuid.UUID) -> list[WaiverRequest]:
    return list(
        db.scalars(select(WaiverRequest).where(WaiverRequest.order_id == order_id).order_by(WaiverRequest.created_at))
    )


def request_waiver(db: Session, order_id: uuid.UUID, data: schemas.WaiverRequestIn, actor: Actor) -> WaiverRequest:
    order = get_locked(db, order_id)
    if order.status != OrderStatus.AWAITING_PAYMENT:
        raise Conflict("ORDER_NOT_AWAITING_PAYMENT", status=order.status.value)
    if any(w.status == WaiverStatus.REQUESTED for w in waivers_for(db, order.id)):
        raise Conflict("WAIVER_ALREADY_REQUESTED")
    return _open_waiver(db, order, data.fee_category, data.reason, actor)


def decide_waiver(db: Session, waiver_id: uuid.UUID, data: schemas.WaiverDecisionIn, actor: Actor) -> WaiverRequest:
    w = db.get(WaiverRequest, waiver_id, with_for_update=True)
    if w is None:
        raise NotFound("waiver_request")
    if w.status != WaiverStatus.REQUESTED:
        raise Conflict("WAIVER_ALREADY_DECIDED", status=w.status.value)
    if w.requested_by == actor.id:
        raise Forbidden("WAIVER_SELF_APPROVAL")
    order = get_locked(db, w.order_id)
    w.decided_by = actor.id
    if not data.approve:
        transition(db, w, WaiverStatus.DECLINED, actor, reason=data.reason)
        return w
    if order.status != OrderStatus.AWAITING_PAYMENT:
        raise Conflict("ORDER_NOT_AWAITING_PAYMENT", status=order.status.value)
    discount = data.discount or 0
    if discount > order.total:
        raise Invalid("DISCOUNT_EXCEEDS_TOTAL", total=order.total)
    w.approved_discount = discount
    transition(db, w, WaiverStatus.APPROVED, actor, reason=data.reason, data={"discount": discount})
    order.fee_category = w.fee_category
    order.waiver_approved_by = actor.id
    order.discount += discount
    _recompute(order)
    payments.record_waiver(db, order.id, discount, actor, data.reason)
    if order.total == 0:
        transition(db, order, OrderStatus.PAID, actor, reason="fully waived")
    return w


def waiver_queue(db: Session, status: WaiverStatus = WaiverStatus.REQUESTED, limit: int = 200) -> list[WaiverRequest]:
    return list(
        db.scalars(
            select(WaiverRequest).where(WaiverRequest.status == status).order_by(WaiverRequest.created_at).limit(limit)
        )
    )


# ---- staff lists -----------------------------------------------------------------------------------


def list_orders(
    db: Session, status: OrderStatus | None, q: str | None, cursor: str | None, limit: int
) -> tuple[list[LabOrder], str | None]:
    stmt = select(LabOrder).where(LabOrder.status != OrderStatus.DRAFT)
    if status is not None:
        stmt = stmt.where(LabOrder.status == status)
    if q:
        try:
            stmt = stmt.where(LabOrder.order_code == codes.parse_order_code(q))
        except codes.CodeMistyped:
            ids = [p.id for p in patients.search(db, q, limit=50)]
            stmt = stmt.where(LabOrder.patient_id.in_(ids)) if ids else stmt.where(LabOrder.id.is_(None))
    stmt = apply_cursor(stmt, LabOrder.created_at, LabOrder.id, cursor, limit)
    rows = list(db.scalars(stmt))
    return page(rows, limit, lambda o: (o.created_at, o.id))


def expire_unpaid(db: Session) -> int:
    """AWAITING_PAYMENT orders older than `order_expiry_days` expire; open gateway payments are cancelled."""
    from app.core.actor import SYSTEM
    from app.modules.payments.models import PaymentMethod, PaymentStatus

    cutoff = clock.now() - timedelta(days=settings_store.get_int(db, "order_expiry_days"))
    n = 0
    for order in db.scalars(
        select(LabOrder)
        .where(LabOrder.status == OrderStatus.AWAITING_PAYMENT, LabOrder.awaiting_payment_at < cutoff)
        .with_for_update(skip_locked=True)
    ):
        for p in payments.for_order(db, order.id):
            if p.method == PaymentMethod.GATEWAY and p.status in (PaymentStatus.INITIATED, PaymentStatus.PENDING):
                transition(db, p, PaymentStatus.CANCELLED, SYSTEM, reason="order expired")
        transition(db, order, OrderStatus.EXPIRED, SYSTEM, reason="not paid in time")
        n += 1
    return n


def counts_by_status(db: Session) -> dict[str, int]:
    rows = db.execute(select(LabOrder.status, func.count()).group_by(LabOrder.status)).all()
    return {str(s.value if hasattr(s, "value") else s): int(n) for s, n in rows}


def overdue_count(db: Session) -> int:
    return int(
        db.scalar(
            select(func.count()).where(
                LabOrder.status == OrderStatus.PENDING_VERIFICATION, LabOrder.sla_due_at < clock.now()
            )
        )
        or 0
    )


# ---- slip ------------------------------------------------------------------------------------------


def print_slip(db: Session, order_id: uuid.UUID, actor: Actor) -> bytes:
    from app.modules.documents import slip

    order = get_locked(db, order_id)
    if order.order_code is None:
        raise Conflict("ORDER_HAS_NO_CODE")
    if order.status in (OrderStatus.REJECTED, OrderStatus.CANCELLED, OrderStatus.EXPIRED):
        raise Conflict("ORDER_CLOSED", status=order.status.value)
    reprint = order.slip_print_count
    pdf = slip.render_slip(db, order, reprint)
    order.slip_print_count += 1
    audit.record(
        db,
        actor,
        "order.slip_reprint" if reprint else "order.slip_print",
        entity_type="lab_order",
        entity_id=order.id,
        patient_id=order.patient_id,
        after={"print_no": reprint + 1},
    )
    return pdf


# ---- output assembly -------------------------------------------------------------------------------


def _patient_brief(p: Patient) -> schemas.PatientBrief:
    return schemas.PatientBrief(
        id=p.id, full_name=p.full_name, full_name_bn=p.full_name_bn, sex=p.sex, age=p.age, mobile=p.mobile
    )


def _items_out(db: Session, order: LabOrder) -> list[schemas.OrderItemOut]:
    tests = {t.id: t for t in db.scalars(select(LabTest).where(LabTest.id.in_([i.test_id for i in order.items])))}
    out = []
    for i in order.active_items:
        item = schemas.OrderItemOut.model_validate(i)
        t = tests.get(i.test_id)
        if t is not None:
            item.specimen_type = t.specimen_type
            item.container_type = t.container_type
            item.fasting_required = t.fasting_required
            item.fasting_hours = t.fasting_hours
            item.prep_en = t.prep_en
            item.prep_bn = t.prep_bn
            item.tat_hours = t.tat_hours
        out.append(item)
    return out


def timeline(order: LabOrder) -> list[schemas.TimelineStep]:
    s = order.status
    after_verify = {
        OrderStatus.AWAITING_PAYMENT,
        OrderStatus.PAID,
        OrderStatus.READY_FOR_COLLECTION,
        OrderStatus.CHECKED_IN,
        OrderStatus.COLLECTED,
        OrderStatus.IN_LAB,
        OrderStatus.COMPLETED,
        OrderStatus.REFUND_PENDING,
        OrderStatus.REFUNDED,
    }
    after_pay = after_verify - {OrderStatus.AWAITING_PAYMENT}
    after_collect = {OrderStatus.COLLECTED, OrderStatus.IN_LAB, OrderStatus.COMPLETED}

    verified: schemas.TimelineStep
    if s in after_verify:
        verified = schemas.TimelineStep(key="verified", state="done", at=order.verified_at)
    elif s == OrderStatus.NEEDS_CLARIFICATION:
        verified = schemas.TimelineStep(key="verified", state="error", note=order.clarification_note)
    elif s == OrderStatus.REJECTED:
        verified = schemas.TimelineStep(key="verified", state="error", note=order.status_reason)
    else:
        verified = schemas.TimelineStep(key="verified", state="current" if s != OrderStatus.CANCELLED else "pending")

    def step(key: Any, done: bool, current: bool, at: Any = None) -> schemas.TimelineStep:
        return schemas.TimelineStep(key=key, state="done" if done else "current" if current else "pending", at=at)

    return [
        schemas.TimelineStep(key="submitted", state="done", at=order.submitted_at),
        verified,
        step("paid", s in after_pay, s == OrderStatus.AWAITING_PAYMENT, order.paid_at),
        step("collected", s in after_collect, s in after_pay - after_collect - {OrderStatus.REFUND_PENDING}),
        step("reported", s == OrderStatus.COMPLETED, s in {OrderStatus.COLLECTED, OrderStatus.IN_LAB}),
    ]


def _base_out(db: Session, order: LabOrder) -> dict[str, Any]:
    patient = patients.get(db, order.patient_id)
    items = _items_out(db, order)
    p = _prescription(db, order)
    tats = [i.tat_hours for i in items if i.tat_hours is not None]
    return {
        "id": order.id,
        "order_code": order.order_code,
        "status": order.status,
        "status_reason": order.status_reason,
        "channel": order.channel,
        "priority": order.priority,
        "fee_category": order.fee_category,
        "patient": _patient_brief(patient),
        "items": items,
        "subtotal": order.subtotal,
        "discount": order.discount,
        "total": order.total,
        "amount_due": max(0, order.total - payments.paid_amount(db, order.id, exclude_waiver=True))
        if order.status == OrderStatus.AWAITING_PAYMENT
        else 0,
        "notes": order.notes,
        "clarification_note": order.clarification_note,
        "submitted_at": order.submitted_at,
        "sla_due_at": order.sla_due_at,
        "verified_at": order.verified_at,
        "needs_fasting": any(i.fasting_required for i in items),
        "max_tat_hours": max(tats) if tats else None,
        "prescription": schemas.PrescriptionBrief(
            id=p.id, image_count=len(p.images), doctor_name=p.doctor_name, status=p.status.value
        )
        if p
        else None,
        "timeline": timeline(order),
        "created_at": order.created_at,
    }


def to_out(db: Session, order: LabOrder) -> schemas.OrderOut:
    return schemas.OrderOut(**_base_out(db, order))


def is_overdue(order: LabOrder) -> bool:
    return (
        order.status == OrderStatus.PENDING_VERIFICATION
        and order.sla_due_at is not None
        and order.sla_due_at < clock.now()
    )


def to_staff_out(db: Session, order: LabOrder) -> schemas.StaffOrderOut:
    return schemas.StaffOrderOut(
        **_base_out(db, order),
        lang=order.lang,
        overdue=is_overdue(order),
        slip_print_count=order.slip_print_count,
        created_by_staff_id=order.created_by_staff_id,
        verified_by_staff_id=order.verified_by_staff_id,
        waiver_approved_by=order.waiver_approved_by,
        waivers=[schemas.WaiverOut.model_validate(w) for w in waivers_for(db, order.id)],
        payments=[schemas.PaymentBrief.model_validate(p) for p in payments.for_order(db, order.id)],
    )


def to_rows(db: Session, orders: list[LabOrder]) -> list[schemas.OrderRow]:
    ids = {o.patient_id for o in orders}
    pts = {p.id: p for p in db.scalars(select(Patient).where(Patient.id.in_(ids)))} if ids else {}
    rows = []
    for o in orders:
        p = pts[o.patient_id]
        rows.append(
            schemas.OrderRow(
                id=o.id,
                order_code=o.order_code,
                status=o.status,
                channel=o.channel,
                priority=o.priority,
                fee_category=o.fee_category,
                patient_name=p.full_name,
                patient_sex=p.sex,
                patient_age=p.age,
                tests=[i.abbreviation for i in o.active_items],
                total=o.total,
                submitted_at=o.submitted_at,
                sla_due_at=o.sla_due_at,
                overdue=is_overdue(o),
            )
        )
    return rows


def search_patient_orders(db: Session, patient_id: uuid.UUID, limit: int = 50) -> list[LabOrder]:
    return list(
        db.scalars(
            select(LabOrder)
            .where(LabOrder.patient_id == patient_id, LabOrder.status != OrderStatus.DRAFT)
            .order_by(LabOrder.created_at.desc())
            .limit(limit)
        )
    )
