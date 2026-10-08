"""Beat job: deliver the SMS outbox every few seconds."""

from __future__ import annotations

from app.db import session_factory
from app.modules.notifications import service
from app.workers.jobs import job


@job("deliver_outbox")
def deliver_outbox() -> dict[str, int]:
    with session_factory()() as db:
        res = service.deliver_pending(db)
        db.commit()
        return res
