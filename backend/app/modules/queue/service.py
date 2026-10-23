"""Token issuing (M4). Numbers come from an atomic daily counter per queue."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core import clock, codes
from app.core.actor import Actor
from app.core.state_machine import transition
from app.modules.queue.models import QueueName, QueueToken, TokenStatus

ACTIVE = (TokenStatus.ISSUED, TokenStatus.CALLED)


def active_token(db: Session, order_id: uuid.UUID) -> QueueToken | None:
    return db.scalar(
        select(QueueToken)
        .where(QueueToken.order_id == order_id, QueueToken.status.in_(ACTIVE))
        .order_by(QueueToken.created_at.desc())
        .limit(1)
    )


def issue(db: Session, order_id: uuid.UUID, queue: QueueName, actor: Actor) -> QueueToken:
    """One active token per order; issuing again returns the existing one."""
    existing = active_token(db, order_id)
    if existing is not None:
        return existing
    day = clock.today()
    number = codes.next_counter(db, f"token:{day.isoformat()}:{queue.value}")
    token = QueueToken(
        id=uuid.uuid4(),
        token_date=day,
        queue=queue,
        number=number,
        order_id=order_id,
        status=TokenStatus.ISSUED,
        issued_by=actor.id if actor.type == "staff" else None,
    )
    db.add(token)
    db.flush()
    return token


def cancel_for_order(db: Session, order_id: uuid.UUID, actor: Actor, reason: str) -> None:
    token = active_token(db, order_id)
    if token is not None and token.status == TokenStatus.ISSUED:
        transition(db, token, TokenStatus.CANCELLED, actor, reason=reason)
