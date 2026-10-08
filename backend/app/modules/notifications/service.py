"""SMS outbox: render bn/en templates, enqueue inside the caller's transaction, deliver with retry."""

from __future__ import annotations

import uuid
from datetime import timedelta
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.core import clock
from app.core.actor import SYSTEM
from app.core.state_machine import transition
from app.db import session_factory
from app.modules.notifications.models import Notification, NotificationStatus
from app.modules.notifications.providers import get_provider

TEMPLATE_DIR = Path(__file__).resolve().parent / "templates"
MAX_ATTEMPTS = 6
_GSM7 = set(
    "@£$¥èéùìòÇ\nØø\rÅåΔ_ΦΓΛΩΠΨΣΘΞÆæßÉ !\"#¤%&'()*+,-./0123456789:;<=>?¡ABCDEFGHIJKLMNOPQRSTUVWXYZÄÖÑÜ§"
    "¿abcdefghijklmnopqrstuvwxyzäöñüà"
)
_BN_DIGITS = str.maketrans("0123456789", "০১২৩৪৫৬৭৮৯")


@lru_cache
def templates(lang: str) -> dict[str, str]:
    data = yaml.safe_load((TEMPLATE_DIR / f"{lang}.yaml").read_text(encoding="utf-8"))
    return {str(k): str(v) for k, v in data.items()}


def render(template_key: str, lang: str, params: dict[str, Any]) -> str:
    lang = lang if lang in ("bn", "en") else "bn"
    return templates(lang)[template_key].format_map(params)


def sms_segments(body: str) -> int:
    """Number of SMS parts: GSM-7 = 160 (153 when split), Unicode = 70 (67 when split)."""
    if all(ch in _GSM7 for ch in body):
        single, multi = 160, 153
    else:
        single, multi = 70, 67
    n = len(body)
    return 1 if n <= single else -(-n // multi)


def money_text(paisa: int, lang: str) -> str:
    taka = f"{paisa // 100:,}" if paisa % 100 == 0 else f"{paisa / 100:,.2f}"
    return taka.translate(_BN_DIGITS) if lang == "bn" else taka


def patient_link(order_code: str) -> str:
    return f"{get_settings().public_base_url.rstrip('/')}/o/{order_code}"


def enqueue(
    db: Session,
    to: str | None,
    template_key: str,
    lang: str,
    params: dict[str, Any],
    *,
    order_id: uuid.UUID | None = None,
    patient_id: uuid.UUID | None = None,
) -> Notification | None:
    """Queue an SMS (no-op when the patient has no mobile number)."""
    if not to:
        return None
    lang = lang if lang in ("bn", "en") else "bn"
    n = Notification(
        id=uuid.uuid4(),
        template_key=template_key,
        lang=lang,
        to=to,
        params=params,
        body=render(template_key, lang, params),
        status=NotificationStatus.PENDING,
        next_attempt_at=clock.now(),
        order_id=order_id,
        patient_id=patient_id,
    )
    db.add(n)
    return n


def send_now(db: Session, to: str, template_key: str, lang: str, params: dict[str, Any], *, redact: str) -> bool:
    """Send synchronously (OTP). The stored body/params have `redact` replaced so no secret is kept."""
    body = render(template_key, lang, params)
    res = get_provider().send(to, body)
    n = Notification(
        id=uuid.uuid4(),
        template_key=template_key,
        lang=lang,
        to=to,
        params={k: ("***" if v == redact else v) for k, v in params.items()},
        body=body.replace(redact, "***"),
        status=NotificationStatus.PENDING,
        attempts=1,
        provider_msg_id=res.provider_msg_id,
        last_error=res.error,
    )
    db.add(n)
    transition(db, n, NotificationStatus.SENT if res.ok else NotificationStatus.FAILED, SYSTEM)
    return res.ok


def _attempt(db: Session, n: Notification) -> bool:
    res = get_provider().send(n.to, n.body)
    n.attempts += 1
    if res.ok:
        n.provider_msg_id = res.provider_msg_id
        n.last_error = None
        transition(db, n, NotificationStatus.SENT, SYSTEM)
        return True
    n.last_error = (res.error or "unknown")[:300]
    if n.attempts >= MAX_ATTEMPTS:
        transition(db, n, NotificationStatus.FAILED, SYSTEM, reason=n.last_error)
    else:
        n.next_attempt_at = clock.now() + timedelta(seconds=min(600, 10 * 2**n.attempts))
    return False


def deliver_pending(db: Session, limit: int = 100) -> dict[str, int]:
    now = clock.now()
    rows = list(
        db.scalars(
            select(Notification)
            .where(
                Notification.status == NotificationStatus.PENDING,
                or_(Notification.next_attempt_at.is_(None), Notification.next_attempt_at <= now),
            )
            .order_by(Notification.created_at)
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
    )
    sent = sum(1 for n in rows if _attempt(db, n))
    return {"picked": len(rows), "sent": sent}


def deliver_one(notification_id: str) -> bool:
    with session_factory()() as db:
        n = db.get(Notification, uuid.UUID(notification_id), with_for_update=True)
        if n is None or n.status != NotificationStatus.PENDING:
            return True
        ok = _attempt(db, n)
        db.commit()
        return ok
