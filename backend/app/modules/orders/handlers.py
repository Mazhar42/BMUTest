"""Domain-event handlers: patient SMS on each verification outcome (ROADMAP M3). They run inside the
transition's transaction, so the outbox row commits (or rolls back) with the state change."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.core import codes, events
from app.modules.notifications import service as notifications
from app.modules.patients import service as patients


def _sms(db: Session, order: object, template: str) -> None:
    from app.modules.orders.models import LabOrder

    assert isinstance(order, LabOrder)
    patient = patients.get(db, order.patient_id)
    code = codes.format_order_code(order.order_code) if order.order_code else ""
    params = {
        "code": code,
        "amount": notifications.money_text(order.total, order.lang),
        "link": notifications.patient_link(order.order_code or ""),
    }
    notifications.enqueue(db, patient.mobile, template, order.lang, params, order_id=order.id, patient_id=patient.id)


@events.on("lab_order", "PENDING_VERIFICATION")
def _submitted(db: Session, e: events.TransitionEvent) -> None:
    if e.from_status == "DRAFT":
        _sms(db, e.entity, "order_submitted")


@events.on("lab_order", "AWAITING_PAYMENT")
def _verified(db: Session, e: events.TransitionEvent) -> None:
    _sms(db, e.entity, "walkin_created" if e.from_status == "DRAFT" else "order_verified")


@events.on("lab_order", "NEEDS_CLARIFICATION")
def _clarify(db: Session, e: events.TransitionEvent) -> None:
    _sms(db, e.entity, "order_clarification")


@events.on("lab_order", "REJECTED")
def _rejected(db: Session, e: events.TransitionEvent) -> None:
    _sms(db, e.entity, "order_rejected")


@events.on("waiver_request", "APPROVED")
def _waiver(db: Session, e: events.TransitionEvent) -> None:
    from app.modules.orders.models import LabOrder

    order = db.get(LabOrder, e.entity.order_id)
    if order is not None:
        # the approval transition fires before the order's amounts are reduced
        remaining = max(0, order.total - (e.entity.approved_discount or 0))
        patient = patients.get(db, order.patient_id)
        notifications.enqueue(
            db,
            patient.mobile,
            "waiver_approved",
            order.lang,
            {
                "code": codes.format_order_code(order.order_code or "000000000000"),
                "amount": notifications.money_text(remaining, order.lang),
            },
            order_id=order.id,
            patient_id=patient.id,
        )
