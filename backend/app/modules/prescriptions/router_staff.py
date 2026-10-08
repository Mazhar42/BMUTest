from __future__ import annotations

import uuid
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, Response, UploadFile

from app.core import audit
from app.core.actor import Actor
from app.deps import DB, require
from app.modules.patients import service as patients
from app.modules.patients.models import Channel
from app.modules.prescriptions import schemas, service
from app.modules.prescriptions.router_common import read_images, to_out

router = APIRouter(prefix="/staff/prescriptions", tags=["staff-prescriptions"])


@router.post("", response_model=schemas.PrescriptionOut, status_code=201)
def upload(
    db: DB,
    actor: Annotated[Actor, Depends(require("order.create_walkin"))],
    patient_id: Annotated[uuid.UUID, Form()],
    files: Annotated[list[UploadFile], File(description="1–3 images (webcam photo of the paper prescription)")],
    doctor_name: Annotated[str | None, Form(max_length=120)] = None,
    prescription_date: Annotated[date | None, Form()] = None,
) -> schemas.PrescriptionOut:
    patient = patients.get(db, patient_id)
    p = service.create(db, patient.id, read_images(files), actor, Channel.HELPDESK, doctor_name, prescription_date)
    db.commit()
    return to_out(p)


@router.get("/{prescription_id}/images/{n}", response_class=Response)
def image(
    prescription_id: uuid.UUID,
    n: int,
    db: DB,
    actor: Annotated[Actor, Depends(require("order.verify", "prescription.view", "order.view"))],
) -> Response:
    p = service.get(db, prescription_id)
    data, ctype = service.image(p, n)
    audit.record(
        db,
        actor,
        "prescription.view",
        entity_type="prescription",
        entity_id=p.id,
        patient_id=p.patient_id,
        after={"page": n},
    )
    db.commit()
    return Response(content=data, media_type=ctype, headers={"Cache-Control": "private, max-age=300"})
