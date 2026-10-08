"""Celery worker + Beat schedule (SMS outbox, payment re-query, holds, reminders, reconciliation…)."""

from __future__ import annotations

from typing import Any

from celery import Celery
from celery.schedules import crontab

from app import models_registry  # noqa: F401
from app.config import get_settings
from app.core import logging as bmu_logging
from app.workers.jobs import JOBS

settings = get_settings()
bmu_logging.configure(settings.log_level)

celery = Celery("bmu", broker=settings.redis_url, backend=settings.redis_url)
celery.conf.update(
    timezone="Asia/Dhaka",
    enable_utc=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_default_retry_delay=10,
)
app = celery


@celery.task(name="bmu.run_job")
def run_job(name: str) -> Any:
    fn = JOBS.get(name)
    return fn() if fn is not None else None


@celery.task(name="bmu.send_notification", bind=True, max_retries=6)
def send_notification(self: Any, notification_id: str) -> None:
    from app.modules.notifications.service import deliver_one

    ok = deliver_one(notification_id)
    if not ok:
        raise self.retry(countdown=min(600, 10 * 2**self.request.retries))


def _every(seconds: float, job: str) -> dict[str, Any]:
    return {"task": "bmu.run_job", "schedule": seconds, "args": (job,)}


def _cron(job: str, **kw: Any) -> dict[str, Any]:
    return {"task": "bmu.run_job", "schedule": crontab(**kw), "args": (job,)}


celery.conf.beat_schedule = {
    "outbox": _every(5.0, "deliver_outbox"),
    "release-expired-holds": _every(60.0, "release_expired_holds"),
    "requery-pending-payments": _every(120.0, "requery_pending_payments"),
    "expire-unpaid-orders": _cron("expire_unpaid_orders", minute=15),
    "materialize-slots": _cron("materialize_slots", hour=0, minute=30),
    "appointment-reminders": _cron("send_reminders", hour=settings.reminder_hour_local, minute=0),
    "no-shows": _cron("mark_no_shows", hour=21, minute=0),
    "daily-snapshot": _cron("daily_snapshot", hour=23, minute=55),
    "reconcile": _cron("auto_reconcile", hour=2, minute=0),
    "verification-sla": _every(300.0, "verification_sla_alerts"),
}
