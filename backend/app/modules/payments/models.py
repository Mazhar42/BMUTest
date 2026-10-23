"""Payments (ROADMAP §7.1, M4): gateway (SSLCommerz / mock), bank teller, counter cash, waiver; refunds;
bank-statement reconciliation."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import BigInteger, ForeignKey, Index, String, Text, UniqueConstraint
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


class ReconciliationStatus(StrEnum):
    UNMATCHED = "UNMATCHED"
    MATCHED = "MATCHED"
    EXCEPTION = "EXCEPTION"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class Payment(Entity):
    __tablename__ = "payment"
    __machine__ = Machine(
        "payment",
        PaymentStatus,
        {
            "INITIATED": {"PENDING", "SUCCESS", "FAILED", "CANCELLED", "EXPIRED"},
            "PENDING": {"SUCCESS", "FAILED", "CANCELLED", "EXPIRED"},
            # A gateway can confirm a payment after we stopped waiting for it or the teller cancelled the
            # attempt (late IPN / re-query): the money is real, so it settles and, if not needed, is refunded.
            "EXPIRED": {"SUCCESS"},
            "CANCELLED": {"SUCCESS"},
            "SUCCESS": {"REFUND_PENDING"},
            "REFUND_PENDING": {"REFUNDED", "SUCCESS"},
        },
        order_id=lambda p: p.order_id,
    )
    __table_args__ = (
        UniqueConstraint("provider", "provider_txn_id"),
        Index("ix_payment_method_paid", "method", "paid_at"),
    )

    order_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("lab_order.id"), index=True)
    method: Mapped[PaymentMethod] = mapped_column(str_enum(PaymentMethod, 16))
    provider: Mapped[str | None] = mapped_column(String(20))
    method_hint: Mapped[str | None] = mapped_column(String(20))  # bkash / nagad / upay / rocket / card
    amount: Mapped[int]  # paisa
    status: Mapped[PaymentStatus] = mapped_column(
        str_enum(PaymentStatus, 16), default=PaymentStatus.INITIATED, index=True
    )
    status_reason: Mapped[str | None] = mapped_column(Text)
    gateway_tran_id: Mapped[str | None] = mapped_column(String(40), unique=True)  # our id sent to the gateway
    redirect_url: Mapped[str | None] = mapped_column(Text)
    provider_txn_id: Mapped[str | None] = mapped_column(String(80))
    bank_receipt_no: Mapped[str | None] = mapped_column(String(40))
    received_by_staff_id: Mapped[uuid.UUID | None] = mapped_column(index=True)
    approved_by_staff_id: Mapped[uuid.UUID | None]
    station: Mapped[str | None] = mapped_column(String(60))
    paid_at: Mapped[datetime | None]
    pending_at: Mapped[datetime | None]
    success_at: Mapped[datetime | None]
    failed_at: Mapped[datetime | None]
    cancelled_at: Mapped[datetime | None]
    expired_at: Mapped[datetime | None]
    refund_pending_at: Mapped[datetime | None]
    refunded_at: Mapped[datetime | None]
    reconciliation_status: Mapped[str] = mapped_column(String(16), default=ReconciliationStatus.UNMATCHED.value)
    reconciliation_note: Mapped[str | None] = mapped_column(Text)


class PaymentEvent(Base):
    """Append-only raw gateway callbacks, validations and re-queries."""

    __tablename__ = "payment_event"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    at: Mapped[datetime] = mapped_column(default=clock.now)
    payment_id: Mapped[uuid.UUID | None] = mapped_column(index=True)
    kind: Mapped[str] = mapped_column(String(30))
    payload: Mapped[dict[str, Any]]


class RefundStatus(StrEnum):
    REQUESTED = "REQUESTED"
    APPROVED = "APPROVED"
    COMPLETED = "COMPLETED"
    REJECTED = "REJECTED"
    FAILED = "FAILED"


class RefundMode(StrEnum):
    PROVIDER = "PROVIDER"  # gateway refund API
    MANUAL = "MANUAL"  # cash handed back / bank transfer, with a reference


class Refund(Entity):
    """Full refund of one payment. Requested by one person, approved by another (ROADMAP M4)."""

    __tablename__ = "refund"
    __machine__ = Machine(
        "refund",
        RefundStatus,
        {
            "REQUESTED": {"APPROVED", "REJECTED"},
            "APPROVED": {"COMPLETED", "FAILED"},
            "FAILED": {"COMPLETED", "APPROVED"},
        },
        order_id=lambda r: r.order_id,
    )

    payment_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("payment.id"), index=True)
    order_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("lab_order.id"), index=True)
    amount: Mapped[int]
    reason: Mapped[str] = mapped_column(Text)
    status: Mapped[RefundStatus] = mapped_column(str_enum(RefundStatus, 12), default=RefundStatus.REQUESTED)
    status_reason: Mapped[str | None] = mapped_column(Text)
    mode: Mapped[RefundMode | None] = mapped_column(str_enum(RefundMode, 10))
    requested_by: Mapped[uuid.UUID | None]  # None = raised by the system (duplicate payment)
    decided_by: Mapped[uuid.UUID | None]
    manual_reference: Mapped[str | None] = mapped_column(String(80))
    provider_ref_id: Mapped[str | None] = mapped_column(String(80))
    approved_at: Mapped[datetime | None]
    completed_at: Mapped[datetime | None]
    rejected_at: Mapped[datetime | None]
    failed_at: Mapped[datetime | None]


class BankColumnMapping(Entity):
    """Per-bank CSV column names for statement imports (ROADMAP §9: mapping configurable per bank)."""

    __tablename__ = "bank_column_mapping"

    bank_name: Mapped[str] = mapped_column(String(80), unique=True)
    date_column: Mapped[str] = mapped_column(String(80))
    amount_column: Mapped[str] = mapped_column(String(80))
    reference_column: Mapped[str] = mapped_column(String(80))
    receipt_column: Mapped[str | None] = mapped_column(String(80))
    date_format: Mapped[str] = mapped_column(String(20), default="%d/%m/%Y")


class BankStatementImport(Entity):
    __tablename__ = "bank_statement_import"

    bank_name: Mapped[str] = mapped_column(String(80))
    filename: Mapped[str] = mapped_column(String(200))
    uploaded_by: Mapped[uuid.UUID | None]
    rows: Mapped[int] = mapped_column(default=0)
    matched: Mapped[int] = mapped_column(default=0)
    exceptions: Mapped[int] = mapped_column(default=0)
    skipped: Mapped[int] = mapped_column(default=0)


class LineMatch(StrEnum):
    MATCHED = "MATCHED"
    UNMATCHED = "UNMATCHED"
    AMOUNT_MISMATCH = "AMOUNT_MISMATCH"
    DUPLICATE = "DUPLICATE"
    RESOLVED = "RESOLVED"


class BankStatementLine(Entity):
    __tablename__ = "bank_statement_line"
    __table_args__ = (UniqueConstraint("bank_name", "fingerprint"),)

    import_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("bank_statement_import.id", ondelete="CASCADE"), index=True)
    bank_name: Mapped[str] = mapped_column(String(80))
    fingerprint: Mapped[str] = mapped_column(String(64))  # sha256 of the normalised row → re-uploads are skipped
    line_no: Mapped[int]
    txn_date: Mapped[date | None]
    amount: Mapped[int]  # paisa
    reference: Mapped[str] = mapped_column(Text, default="")
    receipt_no: Mapped[str | None] = mapped_column(String(80))
    order_code: Mapped[str | None] = mapped_column(String(12), index=True)
    match: Mapped[LineMatch] = mapped_column(str_enum(LineMatch, 16), index=True)
    matched_payment_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("payment.id"))
    note: Mapped[str | None] = mapped_column(Text)
    resolved_by: Mapped[uuid.UUID | None]
    raw: Mapped[dict[str, Any]]
