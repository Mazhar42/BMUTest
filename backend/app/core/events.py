"""In-process domain event handlers, run synchronously inside the same DB transaction
(so an SMS enqueued into the outbox commits — or rolls back — together with the state change)."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from app.core.actor import Actor


@dataclass(frozen=True)
class TransitionEvent:
    entity_type: str
    entity: Any
    from_status: str | None
    to_status: str
    actor: Actor
    reason: str | None


Handler = Callable[[Session, TransitionEvent], None]
_handlers: dict[tuple[str, str], list[Handler]] = defaultdict(list)


def on(entity_type: str, *to_statuses: str) -> Callable[[Handler], Handler]:
    def deco(fn: Handler) -> Handler:
        for status in to_statuses:
            if fn not in _handlers[(entity_type, status)]:
                _handlers[(entity_type, status)].append(fn)
        return fn

    return deco


def dispatch(db: Session, event: TransitionEvent) -> None:
    for fn in _handlers.get((event.entity_type, event.to_status), []):
        fn(db, event)
    for fn in _handlers.get((event.entity_type, "*"), []):
        fn(db, event)
