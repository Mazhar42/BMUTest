"""Cross-cutting tables: audit log (append-only), domain events, counters, runtime settings."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core import clock
from app.db import Base, Entity


class AuditLog(Base):
    """Append-only. A DB trigger (migration 0001) rejects UPDATE and DELETE."""

    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    at: Mapped[datetime] = mapped_column(default=clock.now, index=True)
    actor_type: Mapped[str] = mapped_column(String(16))
    actor_id: Mapped[uuid.UUID | None] = mapped_column(index=True)
    actor_label: Mapped[str | None] = mapped_column(String(120))
    action: Mapped[str] = mapped_column(String(80), index=True)
    entity_type: Mapped[str | None] = mapped_column(String(40))
    entity_id: Mapped[str | None] = mapped_column(String(64))
    patient_id: Mapped[uuid.UUID | None] = mapped_column(index=True)
    before: Mapped[dict[str, Any] | None]
    after: Mapped[dict[str, Any] | None]
    reason: Mapped[str | None] = mapped_column(Text)
    ip: Mapped[str | None] = mapped_column(String(64))
    user_agent: Mapped[str | None] = mapped_column(String(300))

    __table_args__ = (Index("ix_audit_log_entity", "entity_type", "entity_id"),)


class DomainEvent(Base):
    """One row per state transition. Feeds SMS handlers and the KPI queries (ROADMAP §13)."""

    __tablename__ = "domain_event"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    at: Mapped[datetime] = mapped_column(default=clock.now, index=True)
    entity_type: Mapped[str] = mapped_column(String(40))
    entity_id: Mapped[uuid.UUID]
    from_status: Mapped[str | None] = mapped_column(String(40))
    to_status: Mapped[str] = mapped_column(String(40))
    order_id: Mapped[uuid.UUID | None] = mapped_column(index=True)
    actor_type: Mapped[str] = mapped_column(String(16))
    actor_id: Mapped[uuid.UUID | None]
    data: Mapped[dict[str, Any] | None]

    __table_args__ = (Index("ix_domain_event_entity", "entity_type", "to_status", "at"),)


class DailyCounter(Base):
    __tablename__ = "daily_counter"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[int] = mapped_column(BigInteger)


class Setting(Entity):
    """Runtime configuration editable by LAB_ADMIN (SLA hours, paper flags, queue ratio…)."""

    __tablename__ = "setting"

    key: Mapped[str] = mapped_column(String(80), unique=True)
    value: Mapped[dict[str, Any]]
    updated_by: Mapped[uuid.UUID | None]
