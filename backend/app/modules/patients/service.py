"""Accounts, patient profiles (self + family), staff-side search and duplicate detection (ROADMAP M2)."""

from __future__ import annotations

import re
import uuid
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core import audit, clock
from app.core.actor import Actor
from app.core.errors import Conflict, Invalid, NotFound
from app.modules.catalog.service import normalize
from app.modules.patients import schemas
from app.modules.patients.models import Account, Channel, Patient, Relation

_MOBILE = re.compile(r"^(?:\+?88)?0?(1[3-9]\d{8})$")
_BN_DIGITS = str.maketrans("০১২৩৪৫৬৭৮৯", "0123456789")


def normalize_mobile(raw: str) -> str:
    """'01712-345678', '+8801712345678', '০১৭১২৩৪৫৬৭৮' -> '+8801712345678'. Raises INVALID_MOBILE."""
    digits = re.sub(r"[\s\-()]", "", (raw or "").translate(_BN_DIGITS))
    m = _MOBILE.match(digits)
    if not m:
        raise Invalid("INVALID_MOBILE")
    return f"+880{m.group(1)}"


def try_normalize_mobile(raw: str) -> str | None:
    try:
        return normalize_mobile(raw)
    except Invalid:
        return None


def _name_search(p: Patient) -> str:
    return " ".join(x for x in (normalize(p.full_name), normalize(p.full_name_bn or "")) if x)


def snapshot(p: Patient) -> dict[str, Any]:
    return {
        "full_name": p.full_name,
        "sex": p.sex.value,
        "date_of_birth": p.date_of_birth.isoformat() if p.date_of_birth else None,
        "age_years": p.age_years,
        "mobile": p.mobile,
    }


# ---- accounts -------------------------------------------------------------------------------------


def get_or_create_account(db: Session, mobile: str, lang: str | None = None) -> tuple[Account, bool]:
    account = db.scalar(select(Account).where(Account.mobile == mobile).with_for_update())
    if account is not None:
        return account, False
    account = Account(id=uuid.uuid4(), mobile=mobile, preferred_language=lang if lang in ("bn", "en") else "bn")
    db.add(account)
    db.flush()
    return account, True


def get_account(db: Session, account_id: uuid.UUID) -> Account | None:
    return db.get(Account, account_id)


def account_out(account: Account) -> schemas.AccountOut:
    return schemas.AccountOut(
        id=account.id,
        mobile=account.mobile,
        preferred_language=account.preferred_language,
        patients=[schemas.PatientOut.model_validate(p) for p in account.patients],
    )


# ---- patient side (always scoped to the caller's account) ------------------------------------------


def get_for_account(db: Session, account_id: uuid.UUID, patient_id: uuid.UUID) -> Patient:
    """A patient under this account, else 404 (never reveals that the id exists elsewhere)."""
    p = db.get(Patient, patient_id)
    if p is None or p.account_id != account_id:
        raise NotFound("patient")
    return p


def create_for_account(db: Session, account: Account, data: schemas.PatientIn, actor: Actor) -> Patient:
    if data.relation_to_account == Relation.SELF and any(
        p.relation_to_account == Relation.SELF for p in account.patients
    ):
        raise Conflict("SELF_PROFILE_EXISTS")
    mobile = normalize_mobile(data.mobile) if data.mobile else account.mobile
    p = Patient(
        id=uuid.uuid4(),
        account_id=account.id,
        full_name=data.full_name.strip(),
        full_name_bn=(data.full_name_bn or "").strip() or None,
        sex=data.sex,
        date_of_birth=data.date_of_birth,
        age_years=data.age_years,
        age_estimated=data.age_years is not None,
        mobile=mobile,
        relation_to_account=data.relation_to_account,
        hospital_patient_no=data.hospital_patient_no,
        created_channel=Channel.APP,
    )
    p.name_search = _name_search(p)
    db.add(p)
    account.patients.append(p)
    db.flush()
    audit.record(db, actor, "patient.create", entity_type="patient", entity_id=p.id, patient_id=p.id, after=snapshot(p))
    return p


def _apply_update(p: Patient, data: schemas.PatientUpdate) -> None:
    changes = data.model_dump(exclude_unset=True)
    if "mobile" in changes:
        changes["mobile"] = normalize_mobile(changes["mobile"]) if changes["mobile"] else None
    if changes.get("date_of_birth") is not None:
        changes["age_years"] = None
        changes["age_estimated"] = False
    elif changes.get("age_years") is not None:
        changes["date_of_birth"] = None
        changes["age_estimated"] = True
    for k, v in changes.items():
        setattr(p, k, v)
    if p.date_of_birth is None and p.age_years is None:
        raise Invalid("AGE_REQUIRED")
    p.name_search = _name_search(p)


def update_for_account(
    db: Session, account_id: uuid.UUID, patient_id: uuid.UUID, data: schemas.PatientUpdate, actor: Actor
) -> Patient:
    p = get_for_account(db, account_id, patient_id)
    before = snapshot(p)
    _apply_update(p, data)
    audit.record(
        db,
        actor,
        "patient.update",
        entity_type="patient",
        entity_id=p.id,
        patient_id=p.id,
        before=before,
        after=snapshot(p),
    )
    return p


# ---- staff side -----------------------------------------------------------------------------------


def get(db: Session, patient_id: uuid.UUID) -> Patient:
    p = db.get(Patient, patient_id)
    if p is None:
        raise NotFound("patient")
    return p


def search(db: Session, q: str, limit: int = 20) -> list[Patient]:
    q = (q or "").strip()
    if not q:
        return []
    mobile = try_normalize_mobile(q)
    if mobile:
        return list(
            db.scalars(select(Patient).where(Patient.mobile == mobile).order_by(Patient.full_name).limit(limit))
        )
    nq = normalize(q)
    stmt = (
        select(Patient)
        .where(
            or_(
                Patient.hospital_patient_no == q,
                Patient.name_search.like(f"%{nq}%"),
                func.word_similarity(nq, Patient.name_search) > 0.5,
            )
        )
        .order_by(func.word_similarity(nq, Patient.name_search).desc(), Patient.full_name)
        .limit(limit)
    )
    return list(db.scalars(stmt))


def find_duplicates(db: Session, data: schemas.PatientIn, mobile: str | None) -> list[schemas.DuplicateCandidate]:
    found: dict[uuid.UUID, schemas.DuplicateCandidate] = {}
    if mobile:
        for p in db.scalars(select(Patient).where(Patient.mobile == mobile).limit(20)):
            found[p.id] = schemas.DuplicateCandidate(
                id=p.id, full_name=p.full_name, sex=p.sex, age=p.age, mobile=p.mobile, reason="MOBILE"
            )
    nq = normalize(data.full_name)
    probe = Patient(full_name=data.full_name, sex=data.sex, date_of_birth=data.date_of_birth, age_years=data.age_years)
    age = probe.age_on(clock.today())
    similar = db.scalars(
        select(Patient)
        .where(Patient.sex == data.sex, func.similarity(Patient.name_search, nq) > 0.6)
        .order_by(func.similarity(Patient.name_search, nq).desc())
        .limit(10)
    )
    for p in similar:
        if p.id in found:
            continue
        if age is None or p.age is None or abs(p.age - age) <= 1:
            found[p.id] = schemas.DuplicateCandidate(
                id=p.id, full_name=p.full_name, sex=p.sex, age=p.age, mobile=p.mobile, reason="NAME"
            )
    return list(found.values())


def register_by_staff(db: Session, data: schemas.StaffPatientIn, actor: Actor, channel: Channel) -> Patient:
    mobile = normalize_mobile(data.mobile) if data.mobile else None
    if not data.force:
        dups = find_duplicates(db, data, mobile)
        if dups:
            raise Conflict("POSSIBLE_DUPLICATE", candidates=[d.model_dump(mode="json") for d in dups])
    p = Patient(
        id=uuid.uuid4(),
        account_id=None,
        full_name=data.full_name.strip(),
        full_name_bn=(data.full_name_bn or "").strip() or None,
        sex=data.sex,
        date_of_birth=data.date_of_birth,
        age_years=data.age_years,
        age_estimated=data.age_years is not None,
        mobile=mobile,
        nid=data.nid,
        relation_to_account=Relation.SELF,
        hospital_patient_no=data.hospital_patient_no,
        created_channel=channel,
        created_by_staff_id=actor.id,
    )
    p.name_search = _name_search(p)
    db.add(p)
    db.flush()
    audit.record(
        db,
        actor,
        "patient.register",
        entity_type="patient",
        entity_id=p.id,
        patient_id=p.id,
        after={**snapshot(p), "forced": data.force},
    )
    return p


def update_by_staff(db: Session, patient_id: uuid.UUID, data: schemas.PatientUpdate, actor: Actor) -> Patient:
    p = get(db, patient_id)
    before = snapshot(p)
    _apply_update(p, data)
    audit.record(
        db,
        actor,
        "patient.update",
        entity_type="patient",
        entity_id=p.id,
        patient_id=p.id,
        before=before,
        after=snapshot(p),
    )
    return p
