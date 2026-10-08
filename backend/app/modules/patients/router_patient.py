from __future__ import annotations

import uuid

from fastapi import APIRouter

from app.deps import DB, PatientCtx
from app.modules.patients import schemas, service
from app.modules.patients.models import Patient

router = APIRouter(prefix="/patient", tags=["patient-profile"])


@router.get("/me", response_model=schemas.AccountOut)
def me(ctx: PatientCtx) -> schemas.AccountOut:
    return service.account_out(ctx.account)


@router.patch("/me", response_model=schemas.AccountOut)
def update_me(data: schemas.AccountPrefsIn, db: DB, ctx: PatientCtx) -> schemas.AccountOut:
    ctx.account.preferred_language = data.preferred_language
    db.commit()
    return service.account_out(ctx.account)


@router.get("/patients", response_model=list[schemas.PatientOut])
def list_patients(ctx: PatientCtx) -> list[Patient]:
    return list(ctx.account.patients)


@router.post("/patients", response_model=schemas.PatientOut, status_code=201)
def create_patient(data: schemas.PatientIn, db: DB, ctx: PatientCtx) -> Patient:
    p = service.create_for_account(db, ctx.account, data, ctx.actor)
    db.commit()
    return p


@router.get("/patients/{patient_id}", response_model=schemas.PatientOut)
def get_patient(patient_id: uuid.UUID, db: DB, ctx: PatientCtx) -> Patient:
    return service.get_for_account(db, ctx.account.id, patient_id)


@router.patch("/patients/{patient_id}", response_model=schemas.PatientOut)
def update_patient(patient_id: uuid.UUID, data: schemas.PatientUpdate, db: DB, ctx: PatientCtx) -> Patient:
    p = service.update_for_account(db, ctx.account.id, patient_id, data, ctx.actor)
    db.commit()
    return p
