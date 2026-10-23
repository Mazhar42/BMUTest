"""Payments (ROADMAP M4): gateway sessions + IPN settlement, bank teller / counter receipts, waiver payments.

Invariants (tested):
  * settlement is idempotent — a payment row lock plus unique (provider, provider_txn_id); a second IPN or
    teller click changes nothing;
  * the order row is locked before a receipt is created, so two tellers receiving the same code at once
    produce exactly one SUCCESS;
  * gateway callbacks are verified with the provider (never trusted); amount / transaction id / currency
    must match, otherwise the payment is FAILED with the reason (e.g. AMOUNT_MISMATCH);
  * money received for an order that no longer needs it (duplicate payment, cancelled/expired order) is not
    swallowed — a system refund request is raised.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.core import audit, clock, codes, settings_store
from app.core.actor import GATEWAY, SYSTEM, Actor
from app.core.errors import AppError, Conflict, Forbidden, Invalid, NotFound
from app.core.state_machine import can_transition, transition
from app.modules.notifications import service as notifications
from app.modules.orders.models import LabOrder, OrderPriority, OrderStatus
from app.modules.patients import service as patients
from app.modules.payments.adapters import get_provider, online_payments_enabled
from app.modules.payments.adapters.base import Customer, Validation
from app.modules.payments.models import (
    Payment,
    PaymentEvent,
    PaymentMethod,
    PaymentStatus,
    ReconciliationStatus,
    Refund,
    RefundStatus,
)
from app.modules.queue import service as queue
from app.modules.queue.models import QueueName, QueueToken

IN_PERSON = (PaymentMethod.BANK_TELLER, PaymentMethod.COUNTER_CASH)
OPEN_GATEWAY = (PaymentStatus.INITIATED, PaymentStatus.PENDING)
# Statuses after payment: the order no longer needs money.
PAID_OR_LATER = {
    OrderStatus.PAID,
    OrderStatus.READY_FOR_COLLECTION,
    OrderStatus.CHECKED_IN,
    OrderStatus.COLLECTED,
    OrderStatus.IN_LAB,
    OrderStatus.COMPLETED,
    OrderStatus.REFUND_PENDING,
    OrderStatus.REFUNDED,
}
GATEWAY_HINTS = {"bkash", "nagad", "upay", "rocket", "card"}


# ---- queries ---------------------------------------------------------------------------------------


def for_order(db: Session, order_id: uuid.UUID) -> list[Payment]:
    return list(db.scalars(select(Payment).where(Payment.order_id == order_id).order_by(Payment.created_at)))


def paid_amount(db: Session, order_id: uuid.UUID, *, exclude_waiver: bool = False) -> int:
    """Money that counts toward the order total: SUCCESS payments (refund-pending ones no longer count)."""
    total = 0
    for p in for_order(db, order_id):
        if p.status == PaymentStatus.SUCCESS and not (exclude_waiver and p.method == PaymentMethod.WAIVER):
            total += p.amount
    return total


def amount_due(db: Session, order: LabOrder) -> int:
    return max(0, order.total - paid_amount(db, order.id, exclude_waiver=True))


def add_event(db: Session, payment_id: uuid.UUID | None, kind: str, payload: dict[str, Any]) -> None:
    db.add(PaymentEvent(payment_id=payment_id, kind=kind, payload=payload))


def _order_locked(db: Session, order_id: uuid.UUID) -> LabOrder:
    order = db.get(LabOrder, order_id, with_for_update=True)
    if order is None:
        raise NotFound("order")
    return order


def _lang_params(order: LabOrder, amount: int) -> dict[str, Any]:
    return {
        "code": codes.format_order_code(order.order_code or "000000000000"),
        "amount": notifications.money_text(amount, order.lang),
    }


def _sms(db: Session, order: LabOrder, template: str, amount: int, **extra: Any) -> None:
    patient = patients.get(db, order.patient_id)
    notifications.enqueue(
        db,
        patient.mobile,
        template,
        order.lang,
        {**_lang_params(order, amount), **extra},
        order_id=order.id,
        patient_id=patient.id,
    )


# ---- waiver (M3) -----------------------------------------------------------------------------------


def record_waiver(db: Session, order_id: uuid.UUID, amount: int, approver: Actor, reason: str) -> Payment:
    p = Payment(
        id=uuid.uuid4(),
        order_id=order_id,
        method=PaymentMethod.WAIVER,
        provider="WAIVER",
        amount=amount,
        status=PaymentStatus.INITIATED,
        approved_by_staff_id=approver.id,
        reconciliation_status=ReconciliationStatus.NOT_APPLICABLE.value,
    )
    db.add(p)
    p.paid_at = clock.now()
    transition(db, p, PaymentStatus.SUCCESS, approver, reason=reason, data={"amount": amount, "method": "WAIVER"})
    return p


# ---- order classification (teller screen states) ---------------------------------------------------

RECEIVABLE = "RECEIVABLE"
ALREADY_PAID = "ALREADY_PAID"
NOT_VERIFIED = "NOT_VERIFIED"
EXPIRED = "EXPIRED"
CLOSED = "CLOSED"


def order_state(order: LabOrder) -> str:
    s = order.status
    if s == OrderStatus.AWAITING_PAYMENT:
        return RECEIVABLE
    if s in PAID_OR_LATER:
        return ALREADY_PAID
    if s in (OrderStatus.DRAFT, OrderStatus.PENDING_VERIFICATION, OrderStatus.NEEDS_CLARIFICATION):
        return NOT_VERIFIED
    if s == OrderStatus.EXPIRED:
        return EXPIRED
    return CLOSED


@dataclass
class Lookup:
    order: LabOrder
    state: str
    amount_due: int
    paid_payment: Payment | None
    token: QueueToken | None


def lookup(db: Session, ref: str) -> Lookup:
    """By order code in any format (typed or scanned). A mistyped code is rejected by its check digit."""
    code = codes.parse_order_code(ref)
    order = db.scalar(select(LabOrder).where(LabOrder.order_code == code))
    if order is None:
        raise NotFound("order", code=code)
    state = order_state(order)
    paid = None
    if state == ALREADY_PAID:
        paid = next(
            (
                p
                for p in reversed(for_order(db, order.id))
                if p.status != PaymentStatus.FAILED and p.method != PaymentMethod.WAIVER and p.paid_at
            ),
            None,
        )
    return Lookup(
        order=order,
        state=state,
        amount_due=amount_due(db, order) if state == RECEIVABLE else 0,
        paid_payment=paid,
        token=queue.active_token(db, order.id),
    )


# ---- in-person receipts (bank teller / counter) ----------------------------------------------------


@dataclass
class Receipt:
    payment: Payment
    order: LabOrder
    token: QueueToken


def receive_in_person(
    db: Session, ref: str, method: PaymentMethod, actor: Actor, receipt_no: str | None = None
) -> Receipt:
    """ "Received ৳X": record the payment, mark the order PAID, issue the W/P token immediately and SMS it."""
    if method not in IN_PERSON:
        raise Invalid("BAD_PAYMENT_METHOD")
    if method == PaymentMethod.COUNTER_CASH and not settings_store.get_bool(db, "counter_payment_enabled"):
        raise Forbidden("COUNTER_PAYMENT_DISABLED")
    receipt_no = (receipt_no or "").strip() or None
    if (
        method == PaymentMethod.BANK_TELLER
        and settings_store.get_bool(db, "teller_require_receipt_no")
        and not receipt_no
    ):
        raise Invalid("RECEIPT_NO_REQUIRED")

    code = codes.parse_order_code(ref)
    found = db.scalar(select(LabOrder.id).where(LabOrder.order_code == code))
    if found is None:
        raise NotFound("order", code=code)
    order = _order_locked(db, found)  # serialises two tellers on the same code
    state = order_state(order)
    if state == ALREADY_PAID:
        paid = lookup(db, code)
        raise Conflict(
            "ORDER_ALREADY_PAID",
            paid_at=paid.paid_payment.paid_at.isoformat() if paid.paid_payment and paid.paid_payment.paid_at else None,
            method=paid.paid_payment.method.value if paid.paid_payment else None,
            token=paid.token.label if paid.token else None,
        )
    if state == NOT_VERIFIED:
        raise Conflict("ORDER_NOT_VERIFIED", status=order.status.value)
    if state == EXPIRED:
        raise Conflict("ORDER_EXPIRED")
    if state == CLOSED:
        raise Conflict("ORDER_CLOSED", status=order.status.value)

    due = amount_due(db, order)
    if due <= 0:
        raise Conflict("NOTHING_DUE")
    # An online payment still in flight is cancelled; if the gateway confirms later it becomes a refund.
    for p in for_order(db, order.id):
        if p.method == PaymentMethod.GATEWAY and p.status in OPEN_GATEWAY:
            transition(db, p, PaymentStatus.CANCELLED, actor, reason="paid in person")
    payment = Payment(
        id=uuid.uuid4(),
        order_id=order.id,
        method=method,
        provider="TELLER" if method == PaymentMethod.BANK_TELLER else "COUNTER",
        amount=due,
        status=PaymentStatus.INITIATED,
        bank_receipt_no=receipt_no,
        received_by_staff_id=actor.id,
        station=actor.station,
        paid_at=clock.now(),
    )
    db.add(payment)
    db.flush()
    transition(
        db, payment, PaymentStatus.SUCCESS, actor, data={"amount": due, "method": method.value, "receipt": receipt_no}
    )
    transition(db, order, OrderStatus.PAID, actor, data={"payment": str(payment.id)})
    token = queue.issue(db, order.id, QueueName.P if order.priority == OrderPriority.EMERGENCY else QueueName.W, actor)
    _sms(db, order, "payment_received_token", due, token=token.label)
    return Receipt(payment=payment, order=order, token=token)


# ---- gateway ---------------------------------------------------------------------------------------


def start_online_payment(db: Session, order: LabOrder, method_hint: str, actor: Actor) -> Payment:
    """Create a PENDING gateway payment for the amount due and return it with its redirect URL."""
    if not online_payments_enabled():
        raise AppError("ONLINE_PAYMENT_UNAVAILABLE", status_code=503)
    if method_hint not in GATEWAY_HINTS:
        raise Invalid("BAD_PAYMENT_METHOD")
    order = _order_locked(db, order.id)
    if order.status != OrderStatus.AWAITING_PAYMENT:
        raise Conflict("ORDER_NOT_AWAITING_PAYMENT", status=order.status.value)
    due = amount_due(db, order)
    if due <= 0:
        raise Conflict("NOTHING_DUE")
    for p in for_order(db, order.id):
        if p.method == PaymentMethod.GATEWAY and p.status in OPEN_GATEWAY:
            transition(db, p, PaymentStatus.CANCELLED, actor, reason="replaced by a new attempt")
    provider = get_provider()
    payment = Payment(
        id=uuid.uuid4(),
        order_id=order.id,
        method=PaymentMethod.GATEWAY,
        provider=provider.name,
        method_hint=method_hint,
        amount=due,
        status=PaymentStatus.INITIATED,
        gateway_tran_id=f"BMU{uuid.uuid4().hex[:24].upper()}",
    )
    db.add(payment)
    db.flush()
    patient = patients.get(db, order.patient_id)
    payment.redirect_url = provider.initiate(
        payment, order.order_code or "", Customer(patient.full_name, patient.mobile)
    )
    transition(db, payment, PaymentStatus.PENDING, actor, data={"provider": provider.name, "hint": method_hint})
    return payment


def by_tran_id(db: Session, tran_id: str) -> Payment:
    p = db.scalar(select(Payment).where(Payment.gateway_tran_id == tran_id))
    if p is None:
        raise NotFound("payment")
    return p


def _fail(db: Session, p: Payment, status: PaymentStatus, reason: str, v: Validation) -> None:
    if can_transition(p, status):
        transition(db, p, status, GATEWAY, reason=reason, data={"provider_txn": v.provider_txn_id})
    else:
        p.reconciliation_status = ReconciliationStatus.EXCEPTION.value
        p.reconciliation_note = f"late {status.value}: {reason}"


def apply_validation(db: Session, payment_id: uuid.UUID, v: Validation, source: str) -> Payment:
    """Settle a payment from a provider-verified result. Idempotent and safe under concurrent callbacks."""
    p = db.get(Payment, payment_id, with_for_update=True)
    if p is None:
        raise NotFound("payment")
    add_event(db, p.id, source, {**v.raw, "_status": v.status})
    if p.status in (PaymentStatus.SUCCESS, PaymentStatus.REFUND_PENDING, PaymentStatus.REFUNDED):
        add_event(db, p.id, "duplicate_callback", {"status": v.status, "txn": v.provider_txn_id})
        return p
    if v.status == "PENDING":
        return p
    if v.status == "CANCELLED":
        _fail(db, p, PaymentStatus.CANCELLED, "CANCELLED_AT_GATEWAY", v)
        return p
    if v.status != "VALID":
        _fail(db, p, PaymentStatus.FAILED, v.reason or "GATEWAY_FAILED", v)
        return p

    currency = get_settings().payment_currency
    if v.tran_id != p.gateway_tran_id:
        _fail(db, p, PaymentStatus.FAILED, "TRAN_ID_MISMATCH", v)
        return p
    if v.amount != p.amount:
        _fail(db, p, PaymentStatus.FAILED, "AMOUNT_MISMATCH", v)
        return p
    if (v.currency or currency) != currency:
        _fail(db, p, PaymentStatus.FAILED, "CURRENCY_MISMATCH", v)
        return p
    if v.provider_txn_id:
        clash = db.scalar(
            select(Payment.id).where(
                Payment.provider == p.provider, Payment.provider_txn_id == v.provider_txn_id, Payment.id != p.id
            )
        )
        if clash is not None:
            _fail(db, p, PaymentStatus.FAILED, "DUPLICATE_PROVIDER_TXN", v)
            return p
    p.provider_txn_id = v.provider_txn_id
    p.paid_at = clock.now()
    if v.method_hint and not p.method_hint:
        p.method_hint = v.method_hint[:20]
    if not can_transition(p, PaymentStatus.SUCCESS):
        p.reconciliation_status = ReconciliationStatus.EXCEPTION.value
        p.reconciliation_note = f"valid callback after {p.status.value}"
        return p
    transition(db, p, PaymentStatus.SUCCESS, GATEWAY, data={"amount": p.amount, "txn": v.provider_txn_id})
    _settle_order(db, p)
    return p


def _settle_order(db: Session, p: Payment) -> None:
    order = _order_locked(db, p.order_id)
    if order.status == OrderStatus.AWAITING_PAYMENT:
        if paid_amount(db, order.id, exclude_waiver=True) >= order.total:
            transition(db, order, OrderStatus.PAID, GATEWAY, data={"payment": str(p.id)})
            _sms(db, order, "payment_received", p.amount)
        return
    # The order did not need this money (paid another way, cancelled, expired…): raise a refund request.
    from app.modules.payments import refunds

    refunds.request_system(db, p, "DUPLICATE_PAYMENT" if order.status in PAID_OR_LATER else "ORDER_NOT_PAYABLE")


def process_ipn(db: Session, payload: dict[str, str]) -> Payment | None:
    """IPN endpoint body: find our payment by tran_id, verify with the provider, settle."""
    tran_id = payload.get("tran_id", "")
    p = db.scalar(select(Payment).where(Payment.gateway_tran_id == tran_id)) if tran_id else None
    if p is None:
        add_event(db, None, "ipn_unknown_tran", {"tran_id": tran_id[:60]})
        return None
    provider = get_provider(_provider_key(p))
    v = provider.validate(payload)
    return apply_validation(db, p.id, v, "ipn")


def _provider_key(p: Payment) -> str:
    return "mock" if p.provider == "MOCK" else "sslcommerz"


def requery(db: Session, payment_id: uuid.UUID) -> Payment:
    p = db.get(Payment, payment_id)
    if p is None:
        raise NotFound("payment")
    if p.status not in (PaymentStatus.PENDING, PaymentStatus.INITIATED, PaymentStatus.EXPIRED):
        return p
    v = get_provider(_provider_key(p)).query(p, db)
    return apply_validation(db, p.id, v, "requery")


def mock_complete(db: Session, tran_id: str, outcome: str) -> Payment:
    """The mock gateway page: store the outcome, then settle exactly like a real IPN would."""
    s = get_settings()
    if s.env == "prod" or s.payment_provider != "mock":
        raise NotFound("payment")
    p = by_tran_id(db, tran_id)
    status = {"success": "VALID", "fail": "FAILED", "cancel": "CANCELLED"}.get(outcome)
    if status is None:
        raise Invalid("BAD_OUTCOME")
    payload = {
        "tran_id": tran_id,
        "val_id": f"mock-{uuid.uuid4().hex[:12]}",
        "status": status,
        "amount": f"{p.amount / 100:.2f}",
        "currency": s.payment_currency,
        "card_type": p.method_hint or "",
    }
    add_event(db, p.id, "mock_result", payload)
    db.flush()
    return process_ipn(db, payload) or p


# ---- stuck payments (Beat jobs) --------------------------------------------------------------------


def pending_to_requery(db: Session) -> list[uuid.UUID]:
    cutoff = clock.now() - timedelta(minutes=get_settings().payment_pending_requery_minutes)
    return list(
        db.scalars(
            select(Payment.id).where(
                Payment.method == PaymentMethod.GATEWAY,
                Payment.status == PaymentStatus.PENDING,
                Payment.pending_at < cutoff,
            )
        )
    )


def expire_stale(db: Session) -> int:
    """PENDING gateway payments nobody completed within N hours become EXPIRED (a late IPN can still settle)."""
    cutoff = clock.now() - timedelta(hours=get_settings().payment_pending_expire_hours)
    n = 0
    for p in db.scalars(
        select(Payment).where(
            Payment.method == PaymentMethod.GATEWAY, Payment.status.in_(OPEN_GATEWAY), Payment.created_at < cutoff
        )
    ):
        transition(db, p, PaymentStatus.EXPIRED, SYSTEM, reason="no confirmation from the gateway")
        n += 1
    return n


# ---- teller day close ------------------------------------------------------------------------------


@dataclass
class DayClose:
    day: date
    staff_id: uuid.UUID
    count: int
    total: int
    refunded_total: int
    rows: list[Payment]


def day_close(db: Session, staff_id: uuid.UUID, day: date) -> DayClose:
    start, end = clock.day_bounds_utc(day)
    rows = list(
        db.scalars(
            select(Payment)
            .where(
                Payment.method.in_(IN_PERSON),
                Payment.received_by_staff_id == staff_id,
                Payment.paid_at >= start,
                Payment.paid_at < end,
                Payment.status.in_((PaymentStatus.SUCCESS, PaymentStatus.REFUND_PENDING, PaymentStatus.REFUNDED)),
            )
            .order_by(Payment.paid_at)
        )
    )
    refunded = sum(p.amount for p in rows if p.status == PaymentStatus.REFUNDED)
    return DayClose(
        day=day,
        staff_id=staff_id,
        count=len(rows),
        total=sum(p.amount for p in rows),
        refunded_total=refunded,
        rows=rows,
    )


def refund_for(db: Session, payment_id: uuid.UUID) -> list[Refund]:
    return list(db.scalars(select(Refund).where(Refund.payment_id == payment_id)))


def open_refunds(db: Session, status: RefundStatus) -> list[Refund]:
    return list(db.scalars(select(Refund).where(Refund.status == status).order_by(Refund.created_at)))


def audit_view(db: Session, actor: Actor, order: LabOrder) -> None:
    audit.record(db, actor, "payment.lookup", entity_type="lab_order", entity_id=order.id, patient_id=order.patient_id)
