"""Runtime settings: a whitelisted subset of config that LAB_ADMIN can change without a redeploy.
The `.env` value is the default; a `setting` row overrides it."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.core import audit
from app.core.actor import Actor
from app.core.errors import Invalid
from app.core.models import Setting

# key -> python type. Every key must exist on app.config.Settings (its default).
RUNTIME_KEYS: dict[str, type] = {
    "verification_sla_hours": int,
    "order_expiry_days": int,
    "require_paper_hospital_copy": bool,
    "print_bank_copy_when_paid": bool,
    "teller_require_receipt_no": bool,
    "counter_payment_enabled": bool,
    "tube_grouping": str,
    "queue_ratio_a": int,
    "queue_ratio_w": int,
    "reschedule_max": int,
    "reschedule_cutoff_hours": int,
    "checkin_early_minutes": int,
    "checkin_late_minutes": int,
    "release_by_enterer_allowed": bool,
    "share_link_days": int,
    "home_collection_enabled": bool,
}


def get(db: Session, key: str) -> Any:
    if key not in RUNTIME_KEYS:
        raise KeyError(key)
    row = db.scalar(select(Setting).where(Setting.key == key))
    if row is not None:
        return row.value.get("v")
    return getattr(get_settings(), key)


def get_int(db: Session, key: str) -> int:
    return int(get(db, key))


def get_bool(db: Session, key: str) -> bool:
    return bool(get(db, key))


def all_values(db: Session) -> dict[str, Any]:
    return {k: get(db, k) for k in RUNTIME_KEYS}


def put(db: Session, key: str, value: Any, actor: Actor) -> None:
    kind = RUNTIME_KEYS.get(key)
    if kind is None:
        raise Invalid("UNKNOWN_SETTING", key=key)
    if kind is bool and not isinstance(value, bool):
        raise Invalid("SETTING_TYPE", key=key, expected="bool")
    if kind is int and (isinstance(value, bool) or not isinstance(value, int)):
        raise Invalid("SETTING_TYPE", key=key, expected="int")
    if kind is str and not isinstance(value, str):
        raise Invalid("SETTING_TYPE", key=key, expected="str")
    if key == "tube_grouping" and value not in ("container", "container_department"):
        raise Invalid("SETTING_VALUE", key=key)
    before = get(db, key)
    row = db.scalar(select(Setting).where(Setting.key == key))
    if row is None:
        row = Setting(id=uuid.uuid4(), key=key, value={"v": value}, updated_by=actor.id)
        db.add(row)
    else:
        row.value = {"v": value}
        row.updated_by = actor.id
    audit.record(
        db, actor, "setting.update", entity_type="setting", entity_id=key, before={"v": before}, after={"v": value}
    )
