"""Payments (ROADMAP §7.1). M3 uses only the WAIVER method; gateways, teller, counter, refunds and
reconciliation build on this table in M4."""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import BigInteger, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core import clock
from app.core.state_machine import Machine
from app.db import Base, Entity, str_enum


class PaymentMethod(StrEnum):
    GATEWAY = "GATEWAY"
    BANK_TELLER = "BANK_TELLER"
    COUNTER_CASH = "COUNTER_CASH"
    WAIVER = "WAIVER"


class PaymentStatus(StrEnum):
    INITIATED = "INITIATED"
    PENDING = "PENDING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    EXPIRED = "EXPIRED"
    REFUND_PENDING = "REFUND_PENDING"
    REFUNDED = "REFUNDED"


class Payment(Entity):
    __tablename__ = "payment"
    __machine__ = Machine(
        "payment",
        PaymentStatus,
        {
            "INITIATED": {"PENDING", "SUCCESS", "FAILED", "CANCELLED", "EXPIRED"},
            "PENDING": {"SUCCESS", "FAILED", "CANCELLED", "EXPIRED"},
            "SUCCESS": {"REFUND_PENDING"},
            "REFUND_PENDING": {"REFUNDED", "SUCCESS"},
        },
        order_id=lambda p: p.order_id,
    )
    __table_args__ = (UniqueConstraint("provider", "provider_txn_id"),)

    order_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("lab_order.id"), index=True)
    method: Mapped[PaymentMethod] = mapped_column(str_enum(PaymentMethod, 16))
    provider: Mapped[str | None] = mapped_column(String(20))
    amount: Mapped[int]  # paisa
    status: Mapped[PaymentStatus] = mapped_column(str_enum(PaymentStatus, 16), default=PaymentStatus.INITIATED)
    status_reason: Mapped[str | None] = mapped_column(Text)
    gateway_tran_id: Mapped[str | None] = mapped_column(String(40), unique=True)
    provider_txn_id: Mapped[str | None] = mapped_column(String(80))
    bank_receipt_no: Mapped[str | None] = mapped_column(String(40))
    received_by_staff_id: Mapped[uuid.UUID | None]
    approved_by_staff_id: Mapped[uuid.UUID | None]
    paid_at: Mapped[datetime | None]
    success_at: Mapped[datetime | None]
    failed_at: Mapped[datetime | None]
    reconciliation_status: Mapped[str] = mapped_column(String(16), default="UNMATCHED")


class PaymentEvent(Base):
    """Append-only raw gateway callbacks / validations (M4)."""

    __tablename__ = "payment_event"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    at: Mapped[datetime] = mapped_column(default=clock.now)
    payment_id: Mapped[uuid.UUID | None] = mapped_column(index=True)
    kind: Mapped[str] = mapped_column(String(30))
    payload: Mapped[dict[str, Any]]
