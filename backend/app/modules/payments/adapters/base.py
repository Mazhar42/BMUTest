"""Payment provider interface (ROADMAP §9): initiate → redirect, validate a callback, query, refund."""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Literal, Protocol

from sqlalchemy.orm import Session

from app.modules.payments.models import Payment


@dataclass(frozen=True)
class Customer:
    name: str
    mobile: str | None


@dataclass(frozen=True)
class Validation:
    """The provider's verified view of a payment. `amount` is in paisa."""

    status: Literal["VALID", "FAILED", "CANCELLED", "PENDING"]
    tran_id: str | None = None
    amount: int | None = None
    currency: str | None = None
    provider_txn_id: str | None = None
    method_hint: str | None = None
    reason: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class RefundResult:
    ok: bool
    ref_id: str | None = None
    reason: str | None = None


class PaymentProvider(Protocol):
    name: str

    def initiate(self, payment: Payment, order_code: str, customer: Customer) -> str:
        """Create the gateway session and return the URL to send the patient to."""
        ...

    def validate(self, payload: dict[str, str]) -> Validation:
        """Verify an IPN/callback payload with the provider. Never trust the payload itself."""
        ...

    def query(self, payment: Payment, db: Session) -> Validation:
        """Ask the provider for the current state of one payment (stuck-PENDING re-query)."""
        ...

    def refund(self, payment: Payment, amount: int, reason: str, ref_id: str) -> RefundResult: ...


def to_paisa(value: str | float | Decimal | None) -> int | None:
    if value is None or value == "":
        return None
    return int((Decimal(str(value)) * 100).to_integral_value())


def to_taka(paisa: int) -> str:
    return f"{Decimal(paisa) / 100:.2f}"
