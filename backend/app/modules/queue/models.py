"""Queue tokens (ROADMAP §5.2 step 3, §7.1). M4 issues W/P tokens when a patient pays in person; M5 adds
appointment (A) tokens, calling, stations and the display screen on top of this table."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from enum import StrEnum

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.state_machine import Machine
from app.db import Entity, str_enum


class QueueName(StrEnum):
    A = "A"  # appointment (M5)
    W = "W"  # walk-in / paid at the hospital
    P = "P"  # priority (emergency)


class TokenStatus(StrEnum):
    ISSUED = "ISSUED"
    CALLED = "CALLED"
    SERVED = "SERVED"
    NO_SHOW = "NO_SHOW"
    CANCELLED = "CANCELLED"


class QueueToken(Entity):
    __tablename__ = "queue_token"
    __machine__ = Machine(
        "queue_token",
        TokenStatus,
        {
            "ISSUED": {"CALLED", "CANCELLED"},
            "CALLED": {"SERVED", "NO_SHOW", "ISSUED"},
        },
        order_id=lambda t: t.order_id,
    )
    __table_args__ = (UniqueConstraint("token_date", "queue", "number"),)

    token_date: Mapped[date] = mapped_column(index=True)
    queue: Mapped[QueueName] = mapped_column(str_enum(QueueName, 1))
    number: Mapped[int]
    order_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("lab_order.id"), index=True)
    status: Mapped[TokenStatus] = mapped_column(str_enum(TokenStatus, 12), default=TokenStatus.ISSUED)
    status_reason: Mapped[str | None] = mapped_column(String(300))
    issued_by: Mapped[uuid.UUID | None]
    called_at: Mapped[datetime | None]
    served_at: Mapped[datetime | None]
    cancelled_at: Mapped[datetime | None]
    station_no: Mapped[str | None] = mapped_column(String(20))

    @property
    def label(self) -> str:
        """'W-042' (three digits, more when needed)."""
        return f"{self.queue.value}-{self.number:03d}"
