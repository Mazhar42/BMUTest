from __future__ import annotations

import uuid
from datetime import datetime
from enum import StrEnum

import pytest
from sqlalchemy import select

from app.core import events
from app.core.actor import SYSTEM
from app.core.models import AuditLog, DomainEvent
from app.core.state_machine import InvalidTransition, Machine, transition


class S(StrEnum):
    NEW = "NEW"
    DONE = "DONE"
    GONE = "GONE"


class Thing:
    __machine__ = Machine("thing", S, {"NEW": {"DONE"}, "DONE": {"GONE"}})

    def __init__(self) -> None:
        self.id: uuid.UUID | None = None
        self.status = S.NEW
        self.done_at: datetime | None = None


# give the class a `done_at` attribute so the timestamp convention applies
Thing.done_at = None  # type: ignore[attr-defined]


def test_valid_transition_sets_status_timestamp_audit_and_event(db) -> None:  # type: ignore[no-untyped-def]
    seen: list[str] = []
    events.on("thing", "DONE")(lambda _db, e: seen.append(e.to_status))
    t = Thing()
    transition(db, t, S.DONE, SYSTEM, reason="because")
    db.flush()
    assert t.status == S.DONE
    assert t.done_at is not None
    assert seen == ["DONE"]
    audit = db.scalars(select(AuditLog).where(AuditLog.entity_id == str(t.id))).one()
    assert audit.action == "thing.DONE"
    assert audit.before == {"status": "NEW"}
    assert audit.reason == "because"
    ev = db.scalars(select(DomainEvent).where(DomainEvent.entity_id == t.id)).one()
    assert (ev.from_status, ev.to_status) == ("NEW", "DONE")


def test_invalid_transition_raises(db) -> None:  # type: ignore[no-untyped-def]
    t = Thing()
    with pytest.raises(InvalidTransition):
        transition(db, t, S.GONE, SYSTEM)
    assert t.status == S.NEW


def test_machine_rejects_unknown_status() -> None:
    with pytest.raises(ValueError):
        Machine("bad", S, {"NEW": {"NOPE"}})
