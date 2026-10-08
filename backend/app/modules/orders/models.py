from __future__ import annotations

import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import CheckConstraint, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.state_machine import Machine
from app.db import Entity, str_enum
from app.modules.catalog.models import FeeCategory
from app.modules.patients.models import Channel


class OrderStatus(StrEnum):
    DRAFT = "DRAFT"
    PENDING_VERIFICATION = "PENDING_VERIFICATION"
    NEEDS_CLARIFICATION = "NEEDS_CLARIFICATION"
    AWAITING_PAYMENT = "AWAITING_PAYMENT"
    PAID = "PAID"
    READY_FOR_COLLECTION = "READY_FOR_COLLECTION"
    CHECKED_IN = "CHECKED_IN"
    COLLECTED = "COLLECTED"
    IN_LAB = "IN_LAB"
    COMPLETED = "COMPLETED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"
    CANCELLED = "CANCELLED"
    REFUND_PENDING = "REFUND_PENDING"
    REFUNDED = "REFUNDED"


# ROADMAP §7.3. Help-desk orders go DRAFT → AWAITING_PAYMENT (inline verification).
ORDER_TRANSITIONS: dict[str, set[str]] = {
    "DRAFT": {"PENDING_VERIFICATION", "AWAITING_PAYMENT", "CANCELLED"},
    "PENDING_VERIFICATION": {"AWAITING_PAYMENT", "NEEDS_CLARIFICATION", "REJECTED", "CANCELLED"},
    "NEEDS_CLARIFICATION": {"PENDING_VERIFICATION", "REJECTED", "CANCELLED", "EXPIRED"},
    "AWAITING_PAYMENT": {"PAID", "EXPIRED", "CANCELLED"},
    "PAID": {"READY_FOR_COLLECTION", "REFUND_PENDING"},
    "READY_FOR_COLLECTION": {"CHECKED_IN", "REFUND_PENDING"},
    "CHECKED_IN": {"COLLECTED", "READY_FOR_COLLECTION"},
    "COLLECTED": {"IN_LAB"},
    "IN_LAB": {"COMPLETED"},
    "REFUND_PENDING": {"REFUNDED"},
}


class OrderPriority(StrEnum):
    NORMAL = "NORMAL"
    ELDERLY = "ELDERLY"
    DISABLED = "DISABLED"
    EMERGENCY = "EMERGENCY"


class LabOrder(Entity):
    __tablename__ = "lab_order"
    __machine__ = Machine(
        "lab_order", OrderStatus, ORDER_TRANSITIONS, order_id=lambda o: o.id, patient_id=lambda o: o.patient_id
    )

    order_code: Mapped[str | None] = mapped_column(String(12), unique=True)  # assigned at submission
    patient_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("patient.id"), index=True)
    account_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("account.id"), index=True)
    prescription_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("prescription.id"))
    channel: Mapped[Channel] = mapped_column(str_enum(Channel))
    status: Mapped[OrderStatus] = mapped_column(str_enum(OrderStatus), default=OrderStatus.DRAFT, index=True)
    status_reason: Mapped[str | None] = mapped_column(Text)
    priority: Mapped[OrderPriority] = mapped_column(str_enum(OrderPriority, 16), default=OrderPriority.NORMAL)
    fee_category: Mapped[FeeCategory] = mapped_column(str_enum(FeeCategory, 16), default=FeeCategory.GENERAL)
    waiver_approved_by: Mapped[uuid.UUID | None]
    subtotal: Mapped[int] = mapped_column(default=0)  # paisa
    discount: Mapped[int] = mapped_column(default=0)
    total: Mapped[int] = mapped_column(default=0)
    lang: Mapped[str] = mapped_column(String(2), default="bn")  # language for SMS and the slip emphasis
    notes: Mapped[str | None] = mapped_column(Text)
    clarification_note: Mapped[str | None] = mapped_column(Text)
    submitted_at: Mapped[datetime | None] = mapped_column(index=True)
    sla_due_at: Mapped[datetime | None]
    verified_at: Mapped[datetime | None]
    verified_by_staff_id: Mapped[uuid.UUID | None]
    created_by_staff_id: Mapped[uuid.UUID | None]
    slip_print_count: Mapped[int] = mapped_column(default=0)
    # `<status>_at` timestamps written by the state machine
    pending_verification_at: Mapped[datetime | None]
    needs_clarification_at: Mapped[datetime | None]
    awaiting_payment_at: Mapped[datetime | None]
    paid_at: Mapped[datetime | None]
    rejected_at: Mapped[datetime | None]
    cancelled_at: Mapped[datetime | None]
    expired_at: Mapped[datetime | None]
    completed_at: Mapped[datetime | None]

    items: Mapped[list[LabOrderItem]] = relationship(
        back_populates="order", lazy="selectin", order_by="LabOrderItem.created_at", cascade="all, delete-orphan"
    )

    __table_args__ = (
        CheckConstraint("total >= 0 AND discount >= 0 AND discount <= subtotal", name="amounts"),
        Index("ix_lab_order_queue", "status", "sla_due_at"),
    )

    @property
    def active_items(self) -> list[LabOrderItem]:
        return [i for i in self.items if i.status != ItemStatus.CANCELLED]


class ItemStatus(StrEnum):
    ORDERED = "ORDERED"
    COLLECTED = "COLLECTED"
    RECEIVED = "RECEIVED"
    RESULT_ENTERED = "RESULT_ENTERED"
    VERIFIED = "VERIFIED"
    RELEASED = "RELEASED"
    RECOLLECT_REQUIRED = "RECOLLECT_REQUIRED"
    CANCELLED = "CANCELLED"


class LabOrderItem(Entity):
    """One test in an order. Price and names are snapshotted at submission (a later price change does not
    alter existing orders)."""

    __tablename__ = "lab_order_item"
    __machine__ = Machine(
        "lab_order_item",
        ItemStatus,
        {
            "ORDERED": {"COLLECTED", "CANCELLED"},
            "COLLECTED": {"RECEIVED", "RECOLLECT_REQUIRED"},
            "RECEIVED": {"RESULT_ENTERED", "RECOLLECT_REQUIRED"},
            "RESULT_ENTERED": {"VERIFIED", "RECEIVED"},
            "VERIFIED": {"RELEASED"},
            "RECOLLECT_REQUIRED": {"COLLECTED", "CANCELLED"},
        },
        order_id=lambda i: i.order_id,
    )

    order_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("lab_order.id", ondelete="CASCADE"), index=True)
    test_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("lab_test.id"))
    department_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("department.id"), index=True)
    test_code: Mapped[str] = mapped_column(String(30))
    test_name_en: Mapped[str] = mapped_column(String(160))
    test_name_bn: Mapped[str] = mapped_column(String(160))
    abbreviation: Mapped[str] = mapped_column(String(20))
    price_snapshot: Mapped[int]  # paisa
    status: Mapped[ItemStatus] = mapped_column(str_enum(ItemStatus, 24), default=ItemStatus.ORDERED)
    status_reason: Mapped[str | None] = mapped_column(Text)
    specimen_id: Mapped[uuid.UUID | None]
    cancelled_at: Mapped[datetime | None]

    order: Mapped[LabOrder] = relationship(back_populates="items")


class WaiverStatus(StrEnum):
    REQUESTED = "REQUESTED"
    APPROVED = "APPROVED"
    DECLINED = "DECLINED"
    WITHDRAWN = "WITHDRAWN"


class WaiverRequest(Entity):
    """Emergency / free / poor fund / staff concession (ROADMAP §5.4): help desk requests, a user with
    `waiver.approve` decides with a reason. An approval creates a WAIVER payment for the discount."""

    __tablename__ = "waiver_request"
    __machine__ = Machine(
        "waiver_request",
        WaiverStatus,
        {"REQUESTED": {"APPROVED", "DECLINED", "WITHDRAWN"}},
        order_id=lambda w: w.order_id,
    )

    order_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("lab_order.id", ondelete="CASCADE"), index=True)
    fee_category: Mapped[FeeCategory] = mapped_column(str_enum(FeeCategory, 16))
    requested_by: Mapped[uuid.UUID]
    request_reason: Mapped[str] = mapped_column(Text)
    status: Mapped[WaiverStatus] = mapped_column(str_enum(WaiverStatus, 12), default=WaiverStatus.REQUESTED)
    status_reason: Mapped[str | None] = mapped_column(Text)
    decided_by: Mapped[uuid.UUID | None]
    approved_discount: Mapped[int | None]  # paisa
    approved_at: Mapped[datetime | None]
    declined_at: Mapped[datetime | None]
