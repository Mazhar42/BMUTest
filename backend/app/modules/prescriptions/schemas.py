from __future__ import annotations

import uuid
from datetime import date

from pydantic import BaseModel

from app.modules.prescriptions.models import PrescriptionStatus


class PrescriptionOut(BaseModel):
    id: uuid.UUID
    patient_id: uuid.UUID
    image_count: int
    doctor_name: str | None
    prescription_date: date | None
    status: PrescriptionStatus
