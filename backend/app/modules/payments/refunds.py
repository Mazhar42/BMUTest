"""Refunds (ROADMAP M4): requested by one person, approved by another, completed through the provider's
refund API or recorded manually (cash handed back / bank transfer, with a reference)."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core import audit, clock
from app.core.actor import SYSTEM, Actor
from app.core.errors import Conflict, Forbidden, Invalid, NotFound
from app.core.state_machine import can_transition, transition
from app.modules.orders.models import LabOrder, OrderStatus
from app.modules.payments import service
from app.modules.payments.adapters import get_provider
from app.modules.payments.models import Payment, PaymentMethod, PaymentStatus, Refund, RefundMode, RefundStatus
from app.modules.queue import service as queue


def _remaining_covers_total(db: Session, order: LabOrder, leaving: Payment) -> bool:
    paid = sum(
        p.amount
        for p in service.for_order(db, order.id)
        if p.id != leaving.id and p.status == PaymentStatus.SUCCESS and p.method != PaymentMethod.WAIVER
    )
    return paid >= order.total


def _open(db: Session, payment: Payment, reason: str, requested_by: Actor | None) -> Refund:
    if payment.status != PaymentStatus.SUCCESS or payment.method == PaymentMethod.WAIVER:
        raise Conflict("PAYMENT_NOT_REFUNDABLE", status=payment.status.value)
    actor = requested_by or SYSTEM
    refund = Refund(
        id=uuid.uuid4(),
        payment_id=payment.id,
        order_id=payment.order_id,
        amount=payment.amount,
        reason=reason.strip(),
        status=RefundStatus.REQUESTED,
        requested_by=requested_by.id if requested_by else None,
    )
    db.add(refund)
    db.flush()
    audit.record(
        db,
        actor,
        "refund.REQUESTED",
        entity_type="refund",
        entity_id=refund.id,
        after={"payment": str(payment.id), "amount": payment.amount},
        reason=reason,
    )
    transition(db, payment, PaymentStatus.REFUND_PENDING, actor, reason=reason)
    order = service._order_locked(db, payment.order_id)
    # An order that is still covered by other payments (a duplicate payment) is left alone.
    if not _remaining_covers_total(db, order, payment) and can_transition(order, OrderStatus.REFUND_PENDING):
        transition(db, order, OrderStatus.REFUND_PENDING, actor, reason=reason)
    return refund


def request(db: Session, payment_id: uuid.UUID, reason: str, actor: Actor) -> Refund:
    payment = db.get(Payment, payment_id, with_for_update=True)
    if payment is None:
        raise NotFound("payment")
    if db.scalar(
        select(Refund.id).where(
            Refund.payment_id == payment.id, Refund.status.in_((RefundStatus.REQUESTED, RefundStatus.APPROVED))
        )
    ):
        raise Conflict("REFUND_ALREADY_REQUESTED")
    return _open(db, payment, reason, actor)


def request_system(db: Session, payment: Payment, reason: str) -> Refund:
    return _open(db, payment, reason, None)


def approve(db: Session, refund_id: uuid.UUID, actor: Actor, mode: RefundMode, manual_reference: str | None) -> Refund:
    refund = db.get(Refund, refund_id, with_for_update=True)
    if refund is None:
        raise NotFound("refund")
    if refund.status not in (RefundStatus.REQUESTED, RefundStatus.FAILED):
        raise Conflict("REFUND_ALREADY_DECIDED", status=refund.status.value)
    if refund.requested_by is not None and refund.requested_by == actor.id:
        raise Forbidden("REFUND_SELF_APPROVAL")
    payment = db.get(Payment, refund.payment_id, with_for_update=True)
    assert payment is not None
    reference = (manual_reference or "").strip() or None
    if mode == RefundMode.MANUAL and not reference:
        raise Invalid("REFUND_REFERENCE_REQUIRED")
    if mode == RefundMode.PROVIDER and payment.method != PaymentMethod.GATEWAY:
        raise Invalid("REFUND_NEEDS_MANUAL_MODE")

    refund.mode = mode
    refund.decided_by = actor.id
    if refund.status == RefundStatus.REQUESTED:
        transition(db, refund, RefundStatus.APPROVED, actor, data={"mode": mode.value})
    else:
        transition(db, refund, RefundStatus.APPROVED, actor, reason="retry")
    if mode == RefundMode.PROVIDER:
        result = get_provider("mock" if payment.provider == "MOCK" else "sslcommerz").refund(
            payment, refund.amount, refund.reason, str(refund.id)
        )
        if not result.ok:
            transition(db, refund, RefundStatus.FAILED, actor, reason=result.reason or "provider refused the refund")
            return refund
        refund.provider_ref_id = result.ref_id
    else:
        refund.manual_reference = reference
    _complete(db, refund, payment, actor)
    return refund


def _complete(db: Session, refund: Refund, payment: Payment, actor: Actor) -> None:
    transition(db, refund, RefundStatus.COMPLETED, actor, data={"amount": refund.amount})
    transition(db, payment, PaymentStatus.REFUNDED, actor)
    order = service._order_locked(db, payment.order_id)
    if order.status == OrderStatus.REFUND_PENDING:
        transition(db, order, OrderStatus.REFUNDED, actor)
        queue.cancel_for_order(db, order.id, actor, "refunded")
    service._sms(db, order, "refund_completed", refund.amount)


def reject(db: Session, refund_id: uuid.UUID, actor: Actor, reason: str) -> Refund:
    refund = db.get(Refund, refund_id, with_for_update=True)
    if refund is None:
        raise NotFound("refund")
    if refund.status != RefundStatus.REQUESTED:
        raise Conflict("REFUND_ALREADY_DECIDED", status=refund.status.value)
    if refund.requested_by is not None and refund.requested_by == actor.id:
        raise Forbidden("REFUND_SELF_APPROVAL")
    refund.decided_by = actor.id
    transition(db, refund, RefundStatus.REJECTED, actor, reason=reason)
    payment = db.get(Payment, refund.payment_id, with_for_update=True)
    assert payment is not None
    transition(db, payment, PaymentStatus.SUCCESS, actor, reason="refund rejected")
    order = service._order_locked(db, payment.order_id)
    if order.status == OrderStatus.REFUND_PENDING:
        transition(db, order, OrderStatus.PAID, actor, reason="refund rejected")
    return refund


def completed_at_note(refund: Refund) -> str | None:
    return clock.to_local(refund.completed_at).isoformat() if refund.completed_at else None
