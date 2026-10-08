"""Seed step: import the PLACEHOLDER catalog from backend/seed/*.csv (idempotent)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from app.core.actor import Actor
from app.modules.catalog import service

SEED_DIR = Path(__file__).resolve().parents[3] / "seed"
SEED_ACTOR = Actor(type="system", label="seed")


def seed_catalog(db: Session, _demo: bool) -> dict[str, Any]:
    summary: dict[str, Any] = {}
    for kind in ("departments", "tests", "parameters"):
        path = SEED_DIR / f"{kind}.csv"
        if not path.exists():
            continue
        res = service.import_csv(db, kind, path.read_text(encoding="utf-8"), SEED_ACTOR)
        summary[f"catalog_{kind}"] = res.model_dump(exclude={"kind"})
    return summary
