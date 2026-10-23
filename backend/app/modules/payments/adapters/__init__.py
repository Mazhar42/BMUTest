from __future__ import annotations

from app.config import get_settings
from app.core.errors import AppError
from app.modules.payments.adapters.base import PaymentProvider
from app.modules.payments.adapters.mock import MockProvider
from app.modules.payments.adapters.sslcommerz import SslCommerzProvider


def get_provider(name: str | None = None) -> PaymentProvider:
    name = (name or get_settings().payment_provider).lower()
    if name == "mock":
        return MockProvider()
    if name == "sslcommerz":
        return SslCommerzProvider()
    raise AppError("PROVIDER_NOT_AVAILABLE", status_code=503)


def online_payments_enabled() -> bool:
    s = get_settings()
    if s.payment_provider == "sslcommerz":
        return bool(s.sslcommerz_store_id and s.sslcommerz_store_password)
    return s.payment_provider == "mock" and s.env != "prod"
