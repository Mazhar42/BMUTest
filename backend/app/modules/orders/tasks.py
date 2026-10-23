"""Beat job: verification SLA watch (ROADMAP M3). Overdue orders are highlighted in the staff queue;
the job logs a warning so monitoring can alert on it."""

from __future__ import annotations

import logging

from app.db import session_factory
from app.modules.orders import service
from app.workers.jobs import job

log = logging.getLogger("bmu.orders")


@job("verification_sla_alerts")
def verification_sla_alerts() -> dict[str, int]:
    with session_factory()() as db:
        n = service.overdue_count(db)
    if n:
        log.warning("verification SLA breached", extra={"overdue_orders": n})
    return {"overdue": n}


@job("expire_unpaid_orders")
def expire_unpaid_orders() -> dict[str, int]:
    with session_factory()() as db:
        n = service.expire_unpaid(db)
        db.commit()
    return {"expired": n}
