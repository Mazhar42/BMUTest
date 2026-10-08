from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, File, Query, UploadFile
from sqlalchemy import select

from app.core.actor import Actor
from app.core.errors import Invalid, NotFound
from app.deps import DB, require
from app.modules.catalog import schemas, service
from app.modules.catalog.models import Department

router = APIRouter(prefix="/staff/catalog", tags=["staff-catalog"])

View = Annotated[Actor, Depends(require("catalog.view", "catalog.manage", "order.verify", "order.create_walkin"))]
Manage = Annotated[Actor, Depends(require("catalog.manage"))]


@router.get("/departments", response_model=list[schemas.DepartmentOut])
def list_departments(db: DB, _: View) -> list[Department]:
    return list(db.scalars(select(Department).order_by(Department.sort, Department.name_en)))


@router.post("/departments", response_model=schemas.DepartmentOut, status_code=201)
def create_department(data: schemas.DepartmentIn, db: DB, actor: Manage) -> Department:
    d = service.create_department(db, data, actor)
    db.commit()
    return d


@router.put("/departments/{dept_id}", response_model=schemas.DepartmentOut)
def update_department(dept_id: uuid.UUID, data: schemas.DepartmentIn, db: DB, actor: Manage) -> Department:
    d = service.update_department(db, dept_id, data, actor)
    db.commit()
    return d


@router.get("/tests", response_model=list[schemas.TestOut])
def search_tests(
    db: DB,
    _: View,
    q: str | None = None,
    department_id: uuid.UUID | None = None,
    include_inactive: bool = False,
    limit: Annotated[int, Query(ge=1, le=500)] = 50,
) -> list[schemas.TestOut]:
    rows = service.search_tests(db, q, limit, include_inactive=include_inactive, department_id=department_id)
    return [service.to_out(t) for t in rows]


@router.get("/tests/{test_id}", response_model=schemas.TestDetail)
def get_test(test_id: uuid.UUID, db: DB, _: View) -> schemas.TestDetail:
    return service.to_detail(service.get_test(db, test_id))


@router.post("/tests", response_model=schemas.TestDetail, status_code=201)
def create_test(data: schemas.TestIn, db: DB, actor: Manage) -> schemas.TestDetail:
    t = service.create_test(db, data, actor)
    db.commit()
    db.refresh(t)
    return service.to_detail(t)


@router.patch("/tests/{test_id}", response_model=schemas.TestDetail)
def update_test(test_id: uuid.UUID, data: schemas.TestUpdate, db: DB, actor: Manage) -> schemas.TestDetail:
    t = service.update_test(db, test_id, data, actor)
    db.commit()
    db.refresh(t)
    return service.to_detail(t)


@router.post("/tests/{test_id}/prices", response_model=schemas.TestDetail)
def set_price(test_id: uuid.UUID, data: schemas.PriceIn, db: DB, actor: Manage) -> schemas.TestDetail:
    t = service.get_test(db, test_id)
    service.set_price(db, t, data.amount, data.fee_category, actor)
    db.commit()
    db.refresh(t)
    return service.to_detail(t)


@router.put("/tests/{test_id}/parameters", response_model=schemas.TestDetail)
def replace_parameters(
    test_id: uuid.UUID, data: list[schemas.ParameterIO], db: DB, actor: Manage
) -> schemas.TestDetail:
    t = service.replace_parameters(db, test_id, data, actor)
    db.commit()
    db.refresh(t)
    return service.to_detail(t)


@router.post("/import/{kind}", response_model=schemas.ImportResult)
def import_csv(kind: str, db: DB, actor: Manage, file: Annotated[UploadFile, File()]) -> schemas.ImportResult:
    if kind not in service.IMPORTERS:
        raise NotFound("import_kind")
    raw = file.file.read(2_000_000 + 1)
    if len(raw) > 2_000_000:
        raise Invalid("FILE_TOO_LARGE", max_bytes=2_000_000)
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise Invalid("CSV_NOT_UTF8") from exc
    res = service.import_csv(db, kind, text, actor)
    db.commit()
    return res
