"""Payment records. M3: the internal WAIVER provider (no external call). M4 adds gateway/teller/counter."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core import clock
from app.core.actor import Actor
from app.core.state_machine import transition
from app.modules.payments.models import Payment, PaymentMethod, PaymentStatus


def record_waiver(db: Session, order_id: uuid.UUID, amount: int, approver: Actor, reason: str) -> Payment:
    p = Payment(
        id=uuid.uuid4(),
        order_id=order_id,
        method=PaymentMethod.WAIVER,
        provider="WAIVER",
        amount=amount,
        status=PaymentStatus.INITIATED,
        approved_by_staff_id=approver.id,
    )
    db.add(p)
    p.paid_at = clock.now()
    transition(db, p, PaymentStatus.SUCCESS, approver, reason=reason, data={"amount": amount, "method": "WAIVER"})
    return p


def for_order(db: Session, order_id: uuid.UUID) -> list[Payment]:
    return list(db.scalars(select(Payment).where(Payment.order_id == order_id).order_by(Payment.created_at)))


def paid_amount(db: Session, order_id: uuid.UUID, *, exclude_waiver: bool = False) -> int:
    total = 0
    for p in for_order(db, order_id):
        if p.status == PaymentStatus.SUCCESS and not (exclude_waiver and p.method == PaymentMethod.WAIVER):
            total += p.amount
    return total
