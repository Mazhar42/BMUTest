from __future__ import annotations

import uuid
from datetime import date
from typing import Annotated

from fastapi import APIRouter, File, Form, Response, UploadFile

from app.core.errors import NotFound
from app.deps import DB, PatientCtx
from app.modules.patients import service as patients
from app.modules.patients.models import Channel
from app.modules.prescriptions import schemas, service
from app.modules.prescriptions.router_common import read_images, to_out

router = APIRouter(prefix="/patient/prescriptions", tags=["patient-prescriptions"])


@router.post("", response_model=schemas.PrescriptionOut, status_code=201)
def upload(
    db: DB,
    ctx: PatientCtx,
    patient_id: Annotated[uuid.UUID, Form()],
    files: Annotated[list[UploadFile], File(description="1–3 images, each ≤ 1 MB")],
    doctor_name: Annotated[str | None, Form(max_length=120)] = None,
    prescription_date: Annotated[date | None, Form()] = None,
) -> schemas.PrescriptionOut:
    patient = patients.get_for_account(db, ctx.account.id, patient_id)
    p = service.create(db, patient.id, read_images(files), ctx.actor, Channel.APP, doctor_name, prescription_date)
    db.commit()
    return to_out(p)


@router.get("/{prescription_id}/images/{n}", response_class=Response)
def image(prescription_id: uuid.UUID, n: int, db: DB, ctx: PatientCtx) -> Response:
    p = service.get(db, prescription_id)
    patient = patients.get(db, p.patient_id)
    if patient.account_id != ctx.account.id:
        raise NotFound("prescription")
    data, ctype = service.image(p, n)
    return Response(content=data, media_type=ctype, headers={"Cache-Control": "private, max-age=300"})
