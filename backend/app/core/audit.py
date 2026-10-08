"""Append-only audit log writer."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.orm import Session

from app.core.actor import Actor, request_meta
from app.core.models import AuditLog


def _jsonable(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, list | tuple | set):
        return [_jsonable(v) for v in value]
    if value is None or isinstance(value, bool | int | float | str):
        return value
    return str(value)


def record(
    db: Session,
    actor: Actor,
    action: str,
    *,
    entity_type: str | None = None,
    entity_id: Any = None,
    patient_id: uuid.UUID | None = None,
    before: dict[str, Any] | None = None,
    after: dict[str, Any] | None = None,
    reason: str | None = None,
) -> AuditLog:
    ip, ua = request_meta()
    row = AuditLog(
        actor_type=actor.type,
        actor_id=actor.id,
        actor_label=actor.label,
        action=action,
        entity_type=entity_type,
        entity_id=str(entity_id) if entity_id is not None else None,
        patient_id=patient_id,
        before=_jsonable(before) if before is not None else None,
        after=_jsonable(after) if after is not None else None,
        reason=reason,
        ip=actor.ip or ip,
        user_agent=((actor.user_agent or ua) or "")[:300] or None,
    )
    db.add(row)
    return row
