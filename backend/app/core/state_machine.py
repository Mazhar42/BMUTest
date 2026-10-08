"""Generic state machine (ROADMAP §7.3).

`transition(db, entity, to, actor, reason)`:
  * checks the allowed-transitions map of the entity's class (`__machine__`),
  * sets `status` and a `<status>_at` timestamp when the model has that column,
  * writes an AuditLog row and a DomainEvent row,
  * dispatches in-process handlers (SMS, KPIs),
  * raises InvalidTransition otherwise.

Never assign `.status` directly anywhere else.
"""

from __future__ import annotations

import enum
import uuid
from collections.abc import Callable, Iterable, Mapping
from typing import Any

from sqlalchemy.orm import Session

from app.core import audit, clock, events
from app.core.actor import Actor
from app.core.errors import Conflict
from app.core.models import DomainEvent


class InvalidTransition(Conflict):
    def __init__(self, entity_type: str, from_status: str | None, to_status: str) -> None:
        super().__init__("INVALID_TRANSITION", entity=entity_type, from_status=from_status, to_status=to_status)


class Machine:
    def __init__(
        self,
        entity_type: str,
        status_enum: type[enum.Enum],
        transitions: Mapping[str, Iterable[str]],
        *,
        order_id: Callable[[Any], uuid.UUID | None] | None = None,
        patient_id: Callable[[Any], uuid.UUID | None] | None = None,
    ) -> None:
        self.entity_type = entity_type
        self.status_enum = status_enum
        self.transitions: dict[str, frozenset[str]] = {
            str(k): frozenset(str(v) for v in vs) for k, vs in transitions.items()
        }
        self.order_id = order_id
        self.patient_id = patient_id
        valid = {str(m.value) for m in status_enum}
        for frm, tos in self.transitions.items():
            unknown = ({frm} | set(tos)) - valid
            if unknown:
                raise ValueError(f"{entity_type}: unknown statuses {unknown}")

    def can(self, frm: str | None, to: str) -> bool:
        return to in self.transitions.get(str(frm), frozenset())


def _value(v: Any) -> str | None:
    if v is None:
        return None
    return str(v.value) if isinstance(v, enum.Enum) else str(v)


def can_transition(entity: Any, to: str) -> bool:
    machine: Machine = type(entity).__machine__
    return machine.can(_value(entity.status), _value(to) or "")


def transition(
    db: Session,
    entity: Any,
    to: str | enum.Enum,
    actor: Actor,
    reason: str | None = None,
    data: dict[str, Any] | None = None,
) -> None:
    machine: Machine = type(entity).__machine__
    frm = _value(entity.status)
    to_s = _value(to) or ""
    if not machine.can(frm, to_s):
        raise InvalidTransition(machine.entity_type, frm, to_s)

    if entity.id is None:
        entity.id = uuid.uuid4()
    at = clock.now()
    entity.status = machine.status_enum(to_s)
    ts_attr = f"{to_s.lower()}_at"
    if hasattr(type(entity), ts_attr):
        setattr(entity, ts_attr, at)
    if reason is not None and hasattr(type(entity), "status_reason"):
        entity.status_reason = reason

    order_id = machine.order_id(entity) if machine.order_id else None
    patient_id = machine.patient_id(entity) if machine.patient_id else None
    audit.record(
        db,
        actor,
        f"{machine.entity_type}.{to_s}",
        entity_type=machine.entity_type,
        entity_id=entity.id,
        patient_id=patient_id,
        before={"status": frm},
        after={"status": to_s, **(data or {})},
        reason=reason,
    )
    db.add(
        DomainEvent(
            at=at,
            entity_type=machine.entity_type,
            entity_id=entity.id,
            from_status=frm,
            to_status=to_s,
            order_id=order_id,
            actor_type=actor.type,
            actor_id=actor.id,
            data={"reason": reason, **(data or {})} if (reason or data) else None,
        )
    )
    events.dispatch(
        db,
        events.TransitionEvent(machine.entity_type, entity, frm, to_s, actor, reason),
    )
