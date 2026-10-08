"""Multipart helpers shared by the patient and staff prescription endpoints."""

from __future__ import annotations

from fastapi import UploadFile

from app.core.errors import Invalid
from app.modules.prescriptions import schemas
from app.modules.prescriptions.models import Prescription
from app.modules.prescriptions.service import MAX_IMAGE_BYTES, MAX_IMAGES, ImageIn


def read_images(files: list[UploadFile]) -> list[ImageIn]:
    if not 1 <= len(files) <= MAX_IMAGES:
        raise Invalid("PRESCRIPTION_IMAGE_COUNT", min=1, max=MAX_IMAGES)
    out = []
    for f in files:
        data = f.file.read(MAX_IMAGE_BYTES + 1)
        if len(data) > MAX_IMAGE_BYTES:
            raise Invalid("IMAGE_TOO_LARGE", max_bytes=MAX_IMAGE_BYTES)
        out.append(ImageIn(data=data, filename=f.filename))
    return out


def to_out(p: Prescription) -> schemas.PrescriptionOut:
    return schemas.PrescriptionOut(
        id=p.id,
        patient_id=p.patient_id,
        image_count=len(p.images),
        doctor_name=p.doctor_name,
        prescription_date=p.prescription_date,
        status=p.status,
    )
