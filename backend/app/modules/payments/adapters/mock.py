"""Mock gateway for development, tests and E2E. The gateway page is served by our own API
(`/api/v1/public/payments/mock/{tran_id}`); its outcome is stored as a payment_event so every process
(api, worker re-query) sees the same state. Disabled when ENV=prod."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.modules.payments.adapters.base import Customer, RefundResult, Validation, to_paisa
from app.modules.payments.models import Payment, PaymentEvent


class MockProvider:
    name = "MOCK"

    def initiate(self, payment: Payment, order_code: str, customer: Customer) -> str:
        base = get_settings().public_base_url.rstrip("/")
        return f"{base}/api/v1/public/payments/mock/{payment.gateway_tran_id}"

    def validate(self, payload: dict[str, str]) -> Validation:
        status = {"VALID": "VALID", "VALIDATED": "VALID", "CANCELLED": "CANCELLED"}.get(
            str(payload.get("status", "")).upper(), "FAILED"
        )
        return Validation(
            status=status,  # type: ignore[arg-type]
            tran_id=payload.get("tran_id"),
            amount=to_paisa(payload.get("amount")),
            currency=payload.get("currency") or get_settings().payment_currency,
            provider_txn_id=payload.get("val_id") or f"mock-{uuid.uuid4().hex[:12]}",
            method_hint=payload.get("card_type"),
            raw=dict(payload),
        )

    def query(self, payment: Payment, db: Session) -> Validation:
        event = db.scalars(
            select(PaymentEvent)
            .where(PaymentEvent.payment_id == payment.id, PaymentEvent.kind == "mock_result")
            .order_by(PaymentEvent.id.desc())
            .limit(1)
        ).first()
        if event is None:
            return Validation(status="PENDING", tran_id=payment.gateway_tran_id)
        return self.validate(event.payload)

    def refund(self, payment: Payment, amount: int, reason: str, ref_id: str) -> RefundResult:
        return RefundResult(ok=True, ref_id=f"mock-refund-{ref_id[:8]}")
