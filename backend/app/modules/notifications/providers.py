"""SMS adapters (ROADMAP §9). `mock` is used in dev/tests; `sslwireless` is the [BMU] provider adapter,
configured once a BTRC-registered sender ID exists."""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from typing import Protocol

import httpx

from app.config import get_settings

log = logging.getLogger("bmu.sms")


@dataclass(frozen=True)
class SendResult:
    ok: bool
    provider_msg_id: str | None = None
    error: str | None = None


class SmsProvider(Protocol):
    def send(self, to: str, body: str) -> SendResult: ...


@dataclass(frozen=True)
class SentSms:
    to: str
    body: str


class MockSms:
    """Keeps every message in memory (tests read `MockSms.sent`) and, outside tests, prints it to the
    container log unmasked so a developer can read the OTP (ROADMAP M2)."""

    sent: list[SentSms] = []  # noqa: RUF012 — shared on purpose

    def send(self, to: str, body: str) -> SendResult:
        MockSms.sent.append(SentSms(to, body))
        if get_settings().env == "dev":
            print(f"[mock-sms] to={to} | {body}", flush=True)  # dev convenience; the JSON logger would mask it
        return SendResult(ok=True, provider_msg_id=f"mock-{uuid.uuid4().hex[:12]}")

    @classmethod
    def clear(cls) -> None:
        cls.sent.clear()

    @classmethod
    def last_to(cls, to: str) -> SentSms | None:
        return next((m for m in reversed(cls.sent) if m.to == to), None)


class SslWirelessSms:
    """SSL Wireless bulk SMS (JSON API). Endpoint, token and sender id come from .env [BMU]."""

    def send(self, to: str, body: str) -> SendResult:
        s = get_settings()
        if not s.sms_api_url or not s.sms_api_token:
            return SendResult(ok=False, error="SMS provider not configured")
        payload = {
            "api_token": s.sms_api_token,
            "sid": s.sms_sender_id,
            "msisdn": to.lstrip("+"),
            "sms": body,
            "csms_id": uuid.uuid4().hex[:20],
        }
        try:
            r = httpx.post(s.sms_api_url, json=payload, timeout=10.0)
        except httpx.HTTPError as exc:
            return SendResult(ok=False, error=f"network: {type(exc).__name__}")
        if r.status_code != 200:
            return SendResult(ok=False, error=f"http {r.status_code}")
        data = r.json()
        if str(data.get("status_code")) != "200":
            return SendResult(ok=False, error=str(data.get("error_message") or data.get("status"))[:200])
        info = data.get("smsinfo") or [{}]
        return SendResult(ok=True, provider_msg_id=str(info[0].get("reference_id") or payload["csms_id"]))


def get_provider() -> SmsProvider:
    if get_settings().sms_provider == "sslwireless":
        return SslWirelessSms()
    return MockSms()
