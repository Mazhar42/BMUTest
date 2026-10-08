from __future__ import annotations

import uuid
from datetime import datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.state_machine import Machine
from app.db import Entity, str_enum


class NotificationStatus(StrEnum):
    PENDING = "PENDING"
    SENT = "SENT"
    FAILED = "FAILED"


class Notification(Entity):
    """SMS outbox (ROADMAP §9). Rows are written in the same transaction as the state change that
    caused them; the `deliver_outbox` job (Celery Beat) sends them with retry and backoff."""

    __tablename__ = "notification"
    __machine__ = Machine(
        "notification",
        NotificationStatus,
        {"PENDING": {"SENT", "FAILED"}, "FAILED": {"SENT"}},
        order_id=lambda n: n.order_id,
        patient_id=lambda n: n.patient_id,
    )

    channel: Mapped[str] = mapped_column(String(10), default="SMS")
    template_key: Mapped[str] = mapped_column(String(60))
    lang: Mapped[str] = mapped_column(String(2))
    to: Mapped[str] = mapped_column(String(20))
    params: Mapped[dict[str, Any]] = mapped_column(default=dict)
    body: Mapped[str] = mapped_column(Text)
    status: Mapped[NotificationStatus] = mapped_column(
        str_enum(NotificationStatus, 10), default=NotificationStatus.PENDING
    )
    attempts: Mapped[int] = mapped_column(default=0)
    next_attempt_at: Mapped[datetime | None]
    last_error: Mapped[str | None] = mapped_column(String(300))
    provider_msg_id: Mapped[str | None] = mapped_column(String(80))
    sent_at: Mapped[datetime | None]
    failed_at: Mapped[datetime | None]
    order_id: Mapped[uuid.UUID | None] = mapped_column(index=True)
    patient_id: Mapped[uuid.UUID | None] = mapped_column(index=True)

    __table_args__ = (Index("ix_notification_pending", "status", "next_attempt_at"),)
