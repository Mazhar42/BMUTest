"""Beat jobs: re-query gateway payments stuck in PENDING, expire stale ones, re-run bank reconciliation."""

from __future__ import annotations

import logging
from typing import Any

from app.core.errors import AppError
from app.db import session_factory
from app.modules.payments import reconciliation, service
from app.workers.jobs import job

log = logging.getLogger("bmu.payments")


@job("requery_pending_payments")
def requery_pending_payments() -> dict[str, Any]:
    with session_factory()() as db:
        ids = service.pending_to_requery(db)
        expired = service.expire_stale(db)
        db.commit()
    settled = failed = 0
    for pid in ids:
        with session_factory()() as db:  # one transaction per payment: a gateway outage must not block the rest
            try:
                p = service.requery(db, pid)
                db.commit()
                settled += p.status.value == "SUCCESS"
            except AppError:
                db.rollback()
                failed += 1
                log.warning("payment re-query failed", extra={"payment_id": str(pid)})
    return {"checked": len(ids), "settled": settled, "errors": failed, "expired": expired}


@job("auto_reconcile")
def auto_reconcile() -> dict[str, int]:
    with session_factory()() as db:
        res = reconciliation.rematch_open_lines(db)
        db.commit()
        return res
