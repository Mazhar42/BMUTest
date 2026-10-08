from __future__ import annotations

import uuid
from datetime import date, datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.state_machine import Machine
from app.db import Entity, str_enum
from app.modules.patients.models import Channel


class PrescriptionStatus(StrEnum):
    DRAFT = "DRAFT"
    SUBMITTED = "SUBMITTED"
    NEEDS_CLARIFICATION = "NEEDS_CLARIFICATION"
    VERIFIED = "VERIFIED"
    REJECTED = "REJECTED"


class Prescription(Entity):
    """1–3 photographed pages. Staff verify the selected tests against it (no OCR in V1, ROADMAP §2)."""

    __tablename__ = "prescription"
    __machine__ = Machine(
        "prescription",
        PrescriptionStatus,
        {
            "DRAFT": {"SUBMITTED", "VERIFIED"},
            "SUBMITTED": {"VERIFIED", "NEEDS_CLARIFICATION", "REJECTED"},
            "NEEDS_CLARIFICATION": {"SUBMITTED", "REJECTED"},
        },
        patient_id=lambda p: p.patient_id,
    )

    patient_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("patient.id"), index=True)
    images: Mapped[list[Any]] = mapped_column(default=list)  # object keys in the `prescriptions` bucket
    doctor_name: Mapped[str | None] = mapped_column(String(120))
    prescription_date: Mapped[date | None]
    status: Mapped[PrescriptionStatus] = mapped_column(
        str_enum(PrescriptionStatus, 24), default=PrescriptionStatus.DRAFT
    )
    status_reason: Mapped[str | None] = mapped_column(Text)
    channel: Mapped[Channel] = mapped_column(str_enum(Channel))
    uploaded_by_staff_id: Mapped[uuid.UUID | None]
    submitted_at: Mapped[datetime | None]
    verified_at: Mapped[datetime | None]
    verified_by: Mapped[uuid.UUID | None]
    clarification_note: Mapped[str | None] = mapped_column(Text)
    sla_due_at: Mapped[datetime | None]
