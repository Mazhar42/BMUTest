"""Catalog: departments, tests (aliases → search), price history, parameters & reference ranges,
idempotent CSV import (ROADMAP M2)."""

from __future__ import annotations

import csv
import io
import re
import unicodedata
import uuid
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from app.core import audit, clock
from app.core.actor import Actor
from app.core.errors import Conflict, Invalid, NotFound
from app.modules.catalog import schemas
from app.modules.catalog.models import (
    CollectionResource,
    ContainerType,
    Department,
    FeeCategory,
    LabTest,
    LabTestPrice,
    ReferenceRange,
    ResultMode,
    SpecimenType,
    TestParameter,
    ValueType,
)

_PUNCT = re.compile(r"[.\-_/(),:;'\"+]+")
_SPACES = re.compile(r"\s+")


def normalize(text: str) -> str:
    """Lowercase, NFC, punctuation → space. 'S. Creat' → 's creat'."""
    text = unicodedata.normalize("NFC", text or "").lower()
    return _SPACES.sub(" ", _PUNCT.sub(" ", text)).strip()


def build_search_text(t: LabTest) -> str:
    parts = [t.code, t.abbreviation, t.name_en, t.name_bn, *[str(a) for a in (t.aliases or [])]]
    return " | ".join(normalize(p) for p in parts if p)


# ---- prices ----------------------------------------------------------------------------------------


def current_price(
    t: LabTest, fee_category: FeeCategory = FeeCategory.GENERAL, at: datetime | None = None
) -> int | None:
    at = at or clock.now()

    def pick(cat: FeeCategory) -> int | None:
        for p in t.prices:
            if p.fee_category == cat and p.effective_from <= at and (p.effective_to is None or p.effective_to > at):
                return p.amount
        return None

    price = pick(fee_category)
    return price if price is not None or fee_category == FeeCategory.GENERAL else pick(FeeCategory.GENERAL)


def set_price(db: Session, t: LabTest, amount: int, fee_category: FeeCategory, actor: Actor) -> bool:
    """Close the current price and open a new one. Returns False when unchanged."""
    now = clock.now()
    current = next((p for p in t.prices if p.fee_category == fee_category and p.effective_to is None), None)
    if current is not None and current.amount == amount:
        return False
    if current is not None:
        current.effective_to = now
    new = LabTestPrice(
        id=uuid.uuid4(), test_id=t.id, amount=amount, fee_category=fee_category, effective_from=now, created_by=actor.id
    )
    db.add(new)
    t.prices.insert(0, new)
    audit.record(
        db,
        actor,
        "catalog.price_change",
        entity_type="lab_test",
        entity_id=t.id,
        before={"amount": current.amount if current else None},
        after={"amount": amount, "fee_category": fee_category.value},
    )
    return True


def to_out(t: LabTest) -> schemas.TestOut:
    data = schemas.TestOut.model_validate(t, from_attributes=True).model_dump(exclude={"price"})
    return schemas.TestOut(**data, price=current_price(t))


def to_detail(t: LabTest) -> schemas.TestDetail:
    out = to_out(t).model_dump()
    return schemas.TestDetail(
        **out,
        sort=t.sort,
        prices=[schemas.PriceOut.model_validate(p) for p in t.prices],
        parameters=[schemas.ParameterIO.model_validate(p) for p in t.parameters],
    )


# ---- search ----------------------------------------------------------------------------------------


def search_tests(
    db: Session, q: str | None, limit: int = 30, include_inactive: bool = False, department_id: uuid.UUID | None = None
) -> list[LabTest]:
    base = select(LabTest)
    if not include_inactive:
        base = base.where(LabTest.active.is_(True))
    if department_id:
        base = base.where(LabTest.department_id == department_id)
    nq = normalize(q or "")
    if not nq:
        return list(db.scalars(base.order_by(LabTest.sort, LabTest.name_en).limit(limit)))
    tokens = nq.split(" ")
    phrase = func.strpos(LabTest.search_text, nq) > 0
    # every token must prefix-match a word ('s creat' → 's' and 'creat…')
    conds = [or_(LabTest.search_text.like(f"{tok}%"), LabTest.search_text.like(f"% {tok}%")) for tok in tokens]
    stmt = (
        base.where(and_(*conds))
        .order_by(phrase.desc(), func.similarity(LabTest.search_text, nq).desc(), LabTest.name_en)
        .limit(limit)
    )
    rows = list(db.scalars(stmt))
    if rows:
        return rows
    # typo tolerance fallback (pg_trgm)
    fuzzy = (
        base.where(func.word_similarity(nq, LabTest.search_text) > 0.35)
        .order_by(func.word_similarity(nq, LabTest.search_text).desc())
        .limit(limit)
    )
    return list(db.scalars(fuzzy))


def get_test(db: Session, test_id: uuid.UUID) -> LabTest:
    t = db.get(LabTest, test_id)
    if t is None:
        raise NotFound("lab_test")
    return t


# ---- admin CRUD ------------------------------------------------------------------------------------


def create_department(db: Session, data: schemas.DepartmentIn, actor: Actor) -> Department:
    if db.scalar(select(Department).where(Department.code == data.code)):
        raise Conflict("DUPLICATE_CODE")
    d = Department(
        id=uuid.uuid4(), **data.model_dump(mode="json", exclude={"result_mode"}), result_mode=data.result_mode
    )
    db.add(d)
    audit.record(
        db,
        actor,
        "catalog.department_create",
        entity_type="department",
        entity_id=d.id,
        after=data.model_dump(mode="json"),
    )
    return d


def update_department(db: Session, dept_id: uuid.UUID, data: schemas.DepartmentIn, actor: Actor) -> Department:
    d = db.get(Department, dept_id)
    if d is None:
        raise NotFound("department")
    before = schemas.DepartmentOut.model_validate(d).model_dump(mode="json")
    for k, v in data.model_dump(mode="json").items():
        setattr(d, k, ResultMode(v) if k == "result_mode" else v)
    audit.record(
        db,
        actor,
        "catalog.department_update",
        entity_type="department",
        entity_id=d.id,
        before=before,
        after=data.model_dump(mode="json"),
    )
    return d


def create_test(db: Session, data: schemas.TestIn, actor: Actor) -> LabTest:
    if db.scalar(select(LabTest).where(LabTest.code == data.code)):
        raise Conflict("DUPLICATE_CODE")
    if db.get(Department, data.department_id) is None:
        raise NotFound("department")
    t = LabTest(id=uuid.uuid4(), **data.model_dump(exclude={"price"}))
    t.prices = []
    t.search_text = build_search_text(t)
    db.add(t)
    db.flush()
    if data.price is not None:
        set_price(db, t, data.price, FeeCategory.GENERAL, actor)
    audit.record(
        db, actor, "catalog.test_create", entity_type="lab_test", entity_id=t.id, after=data.model_dump(mode="json")
    )
    return t


def update_test(db: Session, test_id: uuid.UUID, data: schemas.TestUpdate, actor: Actor) -> LabTest:
    t = get_test(db, test_id)
    changes = data.model_dump(exclude_unset=True)
    before = {k: getattr(t, k) for k in changes}
    for k, v in changes.items():
        setattr(t, k, v)
    t.search_text = build_search_text(t)
    audit.record(
        db,
        actor,
        "catalog.test_update",
        entity_type="lab_test",
        entity_id=t.id,
        before=before,
        after=data.model_dump(mode="json", exclude_unset=True),
    )
    return t


def replace_parameters(db: Session, test_id: uuid.UUID, params: list[schemas.ParameterIO], actor: Actor) -> LabTest:
    t = get_test(db, test_id)
    t.parameters.clear()
    db.flush()
    for p in params:
        tp = TestParameter(id=uuid.uuid4(), test_id=t.id, **p.model_dump(exclude={"id", "ranges"}))
        tp.ranges = [ReferenceRange(id=uuid.uuid4(), **r.model_dump()) for r in p.ranges]
        t.parameters.append(tp)
    audit.record(
        db,
        actor,
        "catalog.parameters_replace",
        entity_type="lab_test",
        entity_id=t.id,
        after={"parameters": [p.code for p in params]},
    )
    return t


# ---- CSV import (idempotent) ------------------------------------------------------------------------


def _rows(text: str) -> list[dict[str, str]]:
    lines = [ln for ln in text.splitlines() if ln.strip() and not ln.lstrip().startswith("#")]
    return [
        {(k or "").strip(): (v or "").strip() for k, v in row.items()}
        for row in csv.DictReader(io.StringIO("\n".join(lines)))
    ]


def _bool(v: str) -> bool:
    return v.strip().lower() in {"1", "true", "yes", "y"}


def _dec(v: str) -> Decimal | None:
    if v is None or not v.strip():
        return None
    try:
        return Decimal(v.strip())
    except InvalidOperation as exc:
        raise ValueError(f"bad number {v!r}") from exc


def _taka_to_paisa(v: str) -> int:
    d = _dec(v)
    if d is None:
        raise ValueError("price missing")
    return int((d * 100).to_integral_value())


def import_departments(db: Session, text: str, actor: Actor) -> schemas.ImportResult:
    res = schemas.ImportResult(kind="departments")
    for i, row in enumerate(_rows(text), start=2):
        try:
            code = row["code"].upper()
            d = db.scalar(select(Department).where(Department.code == code))
            values: dict[str, Any] = {
                "name_en": row["name_en"],
                "name_bn": row["name_bn"],
                "result_mode": ResultMode(row.get("result_mode") or "STRUCTURED"),
                "sort": int(row.get("sort") or 0),
            }
            if d is None:
                db.add(Department(id=uuid.uuid4(), code=code, **values))
                res.created += 1
            elif any(getattr(d, k) != v for k, v in values.items()):
                for k, v in values.items():
                    setattr(d, k, v)
                res.updated += 1
            else:
                res.unchanged += 1
        except (KeyError, ValueError) as exc:
            res.errors.append(f"line {i}: {exc}")
    db.flush()
    audit.record(db, actor, "catalog.import", after=res.model_dump())
    return res


def import_tests(db: Session, text: str, actor: Actor) -> schemas.ImportResult:
    """Columns: code,name_en,name_bn,abbreviation,aliases(|-separated),department,specimen_type,
    container_type,collection_resource,fasting_required,fasting_hours,prep_en,prep_bn,tat_hours,
    requires_prescription,price_taka[,home_collectable]"""
    res = schemas.ImportResult(kind="tests")
    depts = {d.code: d for d in db.scalars(select(Department))}
    for i, row in enumerate(_rows(text), start=2):
        try:
            dept = depts.get(row["department"].upper())
            if dept is None:
                raise ValueError(f"unknown department {row['department']!r}")
            values: dict[str, Any] = {
                "name_en": row["name_en"],
                "name_bn": row["name_bn"],
                "abbreviation": row.get("abbreviation") or row["code"],
                "aliases": [a.strip() for a in (row.get("aliases") or "").split("|") if a.strip()],
                "department_id": dept.id,
                "specimen_type": SpecimenType(row["specimen_type"]),
                "container_type": ContainerType(row["container_type"]),
                "collection_resource": CollectionResource(row["collection_resource"]),
                "fasting_required": _bool(row.get("fasting_required", "")),
                "fasting_hours": int(row["fasting_hours"]) if row.get("fasting_hours") else None,
                "prep_en": row.get("prep_en") or None,
                "prep_bn": row.get("prep_bn") or None,
                "tat_hours": int(row.get("tat_hours") or 24),
                "requires_prescription": _bool(row.get("requires_prescription", "true")),
                "home_collectable": _bool(row.get("home_collectable", "true")),
            }
            price = _taka_to_paisa(row["price_taka"])
            code = row["code"].upper()
            t = db.scalar(select(LabTest).where(LabTest.code == code))
            if t is None:
                t = LabTest(id=uuid.uuid4(), code=code, sort=i, **values)
                t.prices = []
                t.search_text = build_search_text(t)
                db.add(t)
                db.flush()
                res.created += 1
            elif any(getattr(t, k) != v for k, v in values.items()):
                for k, v in values.items():
                    setattr(t, k, v)
                t.search_text = build_search_text(t)
                res.updated += 1
            else:
                res.unchanged += 1
            if set_price(db, t, price, FeeCategory.GENERAL, actor):
                res.price_changes += 1
        except (KeyError, ValueError) as exc:
            res.errors.append(f"line {i}: {exc}")
    db.flush()
    audit.record(db, actor, "catalog.import", after=res.model_dump())
    return res


def import_parameters(db: Session, text: str, actor: Actor) -> schemas.ImportResult:
    """One row per reference range. Columns: test_code,param_code,name,unit,decimals,sort,value_type,
    critical_low,critical_high,analyzer_code,sex,age_min_days,age_max_days,low,high,range_text.
    Parameters of a test listed in the file are replaced as a whole (idempotent)."""
    res = schemas.ImportResult(kind="parameters")
    grouped: dict[str, dict[str, schemas.ParameterIO]] = {}
    for i, row in enumerate(_rows(text), start=2):
        try:
            tcode, pcode = row["test_code"].upper(), row["param_code"]
            params = grouped.setdefault(tcode, {})
            p = params.get(pcode)
            if p is None:
                p = schemas.ParameterIO(
                    code=pcode,
                    name=row["name"],
                    unit=row.get("unit") or None,
                    decimals=int(row.get("decimals") or 1),
                    sort=int(row.get("sort") or len(params)),
                    value_type=ValueType(row.get("value_type") or "NUMERIC"),
                    critical_low=_dec(row.get("critical_low", "")),
                    critical_high=_dec(row.get("critical_high", "")),
                    analyzer_code=row.get("analyzer_code") or None,
                )
                params[pcode] = p
            if any(row.get(k) for k in ("low", "high", "range_text")):
                p.ranges.append(
                    schemas.RangeIO(
                        sex=row.get("sex") or None,
                        age_min_days=int(row["age_min_days"]) if row.get("age_min_days") else None,
                        age_max_days=int(row["age_max_days"]) if row.get("age_max_days") else None,
                        low=_dec(row.get("low", "")),
                        high=_dec(row.get("high", "")),
                        text=row.get("range_text") or None,
                    )
                )
        except (KeyError, ValueError) as exc:
            res.errors.append(f"line {i}: {exc}")
    for tcode, params in grouped.items():
        t = db.scalar(select(LabTest).where(LabTest.code == tcode))
        if t is None:
            res.errors.append(f"unknown test {tcode}")
            continue
        existing = [schemas.ParameterIO.model_validate(p).model_dump(exclude={"id"}) for p in t.parameters]
        wanted = [p.model_dump(exclude={"id"}) for p in params.values()]
        if _canon(existing) == _canon(wanted):
            res.unchanged += 1
            continue
        replace_parameters(db, t.id, list(params.values()), actor)
        res.updated += 1
    db.flush()
    return res


def _canon(params: list[dict[str, Any]]) -> list[dict[str, Any]]:
    def norm(v: Any) -> Any:
        if isinstance(v, Decimal):
            return str(v.normalize())
        if isinstance(v, list):
            return [norm(x) for x in v]
        if isinstance(v, dict):
            return {k: norm(x) for k, x in sorted(v.items())}
        return v

    return sorted((norm(p) for p in params), key=lambda p: p["code"])


IMPORTERS = {"departments": import_departments, "tests": import_tests, "parameters": import_parameters}


def import_csv(db: Session, kind: str, text: str, actor: Actor) -> schemas.ImportResult:
    fn = IMPORTERS.get(kind)
    if fn is None:
        raise Invalid("UNKNOWN_IMPORT_KIND", kind=kind)
    return fn(db, text, actor)
