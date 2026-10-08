from __future__ import annotations

import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.security import EncryptedString
from app.db import Entity, str_enum
from app.modules.identity.permissions import Role


class Staff(Entity):
    __tablename__ = "staff"

    username: Mapped[str] = mapped_column(String(60), unique=True)
    full_name: Mapped[str] = mapped_column(String(120))
    full_name_bn: Mapped[str | None] = mapped_column(String(120))
    designation: Mapped[str | None] = mapped_column(String(120))
    mobile: Mapped[str | None] = mapped_column(String(20))
    password_hash: Mapped[str] = mapped_column(String(200))
    pin_hash: Mapped[str | None] = mapped_column(String(200))
    totp_secret: Mapped[str | None] = mapped_column(EncryptedString())
    totp_pending_secret: Mapped[str | None] = mapped_column(EncryptedString())
    totp_enabled: Mapped[bool] = mapped_column(default=False)
    is_active: Mapped[bool] = mapped_column(default=True)
    failed_logins: Mapped[int] = mapped_column(default=0)
    locked_until: Mapped[datetime | None]
    preferred_language: Mapped[str] = mapped_column(String(2), default="en")
    must_change_password: Mapped[bool] = mapped_column(default=False)

    roles: Mapped[list[StaffRole]] = relationship(back_populates="staff", cascade="all, delete-orphan", lazy="selectin")


class StaffRole(Entity):
    __tablename__ = "staff_role"
    __table_args__ = (UniqueConstraint("staff_id", "role", "department_id"),)

    staff_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("staff.id", ondelete="CASCADE"), index=True)
    role: Mapped[Role] = mapped_column(str_enum(Role))
    # Department-scoped roles (TECHNICIAN, PATHOLOGIST).
    department_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("department.id"))

    staff: Mapped[Staff] = relationship(back_populates="roles")


class StaffSession(Entity):
    """A staff login. 12-hour lifetime, 30-minute idle lock; records the station/counter."""

    __tablename__ = "staff_session"

    staff_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("staff.id", ondelete="CASCADE"), index=True)
    station: Mapped[str | None] = mapped_column(String(60))
    expires_at: Mapped[datetime]
    last_seen_at: Mapped[datetime]
    revoked_at: Mapped[datetime | None]
    ip: Mapped[str | None] = mapped_column(String(64))
    user_agent: Mapped[str | None] = mapped_column(String(300))


class DeviceKind(StrEnum):
    DISPLAY = "DISPLAY"
    KIOSK = "KIOSK"
    ANALYZER = "ANALYZER"


class Device(Entity):
    """Long-lived device token for queue displays, kiosks and analyzer middleware."""

    __tablename__ = "device"

    name: Mapped[str] = mapped_column(String(80))
    kind: Mapped[DeviceKind] = mapped_column(str_enum(DeviceKind))
    queue_id: Mapped[str] = mapped_column(String(40), default="main")
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    is_active: Mapped[bool] = mapped_column(default=True)
    last_seen_at: Mapped[datetime | None]
    created_by: Mapped[uuid.UUID | None]
