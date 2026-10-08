from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Query

from app.core.errors import NotFound
from app.deps import DB, PatientCtx
from app.modules.catalog import schemas, service

router = APIRouter(prefix="/patient/catalog", tags=["patient-catalog"])


@router.get("/tests", response_model=list[schemas.TestOut])
def search_tests(
    db: DB, _: PatientCtx, q: str | None = None, limit: Annotated[int, Query(ge=1, le=100)] = 30
) -> list[schemas.TestOut]:
    return [service.to_out(t) for t in service.search_tests(db, q, limit)]


@router.get("/tests/{test_id}", response_model=schemas.TestOut)
def get_test(test_id: uuid.UUID, db: DB, _: PatientCtx) -> schemas.TestOut:
    t = service.get_test(db, test_id)
    if not t.active:
        raise NotFound("lab_test")
    return service.to_out(t)
