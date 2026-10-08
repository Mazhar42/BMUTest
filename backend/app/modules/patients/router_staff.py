from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.core import audit
from app.core.actor import Actor
from app.deps import DB, require
from app.modules.patients import schemas, service
from app.modules.patients.models import Channel, Patient

router = APIRouter(prefix="/staff/patients", tags=["staff-patients"])

Search = Annotated[Actor, Depends(require("patient.search", "patient.register", "order.create_walkin"))]


@router.get("", response_model=list[schemas.StaffPatientOut])
def search(db: DB, actor: Search, q: Annotated[str, Query(min_length=2, max_length=80)]) -> list[Patient]:
    from app.modules.orders import service as orders  # code search resolves through the orders module

    rows = service.search(db, q)
    by_code = orders.patient_for_code(db, q)
    if by_code is not None and all(p.id != by_code.id for p in rows):
        rows.insert(0, by_code)
    audit.record(db, actor, "patient.search", after={"q_len": len(q), "hits": len(rows)})
    db.commit()
    return rows


@router.post("/duplicates", response_model=list[schemas.DuplicateCandidate])
def duplicates(data: schemas.StaffPatientIn, db: DB, _: Search) -> list[schemas.DuplicateCandidate]:
    mobile = service.normalize_mobile(data.mobile) if data.mobile else None
    return service.find_duplicates(db, data, mobile)


@router.post("", response_model=schemas.StaffPatientOut, status_code=201)
def register(
    data: schemas.StaffPatientIn, db: DB, actor: Annotated[Actor, Depends(require("patient.register"))]
) -> Patient:
    p = service.register_by_staff(db, data, actor, Channel.HELPDESK)
    db.commit()
    return p


@router.get("/{patient_id}", response_model=schemas.StaffPatientOut)
def get_patient(
    patient_id: uuid.UUID, db: DB, actor: Annotated[Actor, Depends(require("patient.view", "patient.search"))]
) -> Patient:
    p = service.get(db, patient_id)
    audit.record(db, actor, "patient.view", entity_type="patient", entity_id=p.id, patient_id=p.id)
    db.commit()
    return p


@router.patch("/{patient_id}", response_model=schemas.StaffPatientOut)
def update_patient(
    patient_id: uuid.UUID,
    data: schemas.PatientUpdate,
    db: DB,
    actor: Annotated[Actor, Depends(require("patient.register"))],
) -> Patient:
    p = service.update_by_staff(db, patient_id, data, actor)
    db.commit()
    return p
