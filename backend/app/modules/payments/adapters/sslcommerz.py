"""SSLCommerz (pilot primary gateway, ROADMAP §9): bKash, Nagad, Upay, Rocket, cards, internet banking.

Flow: create session → redirect → IPN to /public/payments/sslcommerz/ipn → **Validation API with val_id**
→ compare tran_id, amount, currency → SUCCESS. The browser success redirect is never trusted.
Sandbox endpoints are used while SSLCOMMERZ_SANDBOX=true. [BMU] needs a merchant account in its own name."""

from __future__ import annotations

import logging
from typing import Any

import httpx
from sqlalchemy.orm import Session

from app.config import get_settings
from app.core.errors import AppError
from app.modules.payments.adapters.base import Customer, RefundResult, Validation, to_paisa, to_taka
from app.modules.payments.models import Payment

log = logging.getLogger("bmu.payments.sslcommerz")

# SSLCommerz channel codes to pre-select a method on the gateway page.
_GATEWAY_CODES = {
    "bkash": "bkash",
    "nagad": "nagad",
    "upay": "upay",
    "rocket": "dbblmobilebanking",
    "card": "visa,master,amex",
}
_VALIDATION_PATH = "/validator/api/validationserverAPI.php"
_MERCHANT_PATH = "/validator/api/merchantTransIDvalidationAPI.php"


class SslCommerzProvider:
    name = "SSLCOMMERZ"

    def __init__(self, client: httpx.Client | None = None) -> None:
        self._client = client

    @property
    def _base(self) -> str:
        sandbox = get_settings().sslcommerz_sandbox
        return "https://sandbox.sslcommerz.com" if sandbox else "https://securepay.sslcommerz.com"

    def _http(self) -> httpx.Client:
        return self._client or httpx.Client(timeout=15.0)

    @staticmethod
    def _creds() -> dict[str, str]:
        s = get_settings()
        if not s.sslcommerz_store_id or not s.sslcommerz_store_password:
            raise AppError("GATEWAY_NOT_CONFIGURED", status_code=503)
        return {"store_id": s.sslcommerz_store_id, "store_passwd": s.sslcommerz_store_password}

    def _get(self, path: str, params: dict[str, str]) -> dict[str, Any]:
        try:
            r = self._http().get(f"{self._base}{path}", params={**self._creds(), **params, "format": "json"})
            r.raise_for_status()
            data = r.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise AppError("GATEWAY_UNAVAILABLE", status_code=502) from exc
        return data if isinstance(data, dict) else {"element": data}

    def initiate(self, payment: Payment, order_code: str, customer: Customer) -> str:
        s = get_settings()
        api = s.public_base_url.rstrip("/") + "/api/v1/public/payments/sslcommerz"
        form = {
            **self._creds(),
            "total_amount": to_taka(payment.amount),
            "currency": s.payment_currency,
            "tran_id": payment.gateway_tran_id or "",
            "success_url": f"{api}/success",
            "fail_url": f"{api}/fail",
            "cancel_url": f"{api}/cancel",
            "ipn_url": f"{api}/ipn",
            "cus_name": customer.name[:50] or "Patient",
            "cus_email": "noreply@invalid.example",
            "cus_add1": "Dhaka",
            "cus_city": "Dhaka",
            "cus_country": "Bangladesh",
            "cus_phone": (customer.mobile or "01700000000").lstrip("+"),
            "shipping_method": "NO",
            "product_name": f"Lab tests {order_code}",
            "product_category": "Healthcare",
            "product_profile": "general",
            "value_a": order_code,
        }
        if payment.method_hint in _GATEWAY_CODES:
            form["multi_card_name"] = _GATEWAY_CODES[payment.method_hint]
        try:
            r = self._http().post(f"{self._base}/gwprocess/v4/api.php", data=form)
            r.raise_for_status()
            data = r.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise AppError("GATEWAY_UNAVAILABLE", status_code=502) from exc
        url = data.get("GatewayPageURL")
        if data.get("status") != "SUCCESS" or not url:
            log.warning("sslcommerz session failed", extra={"reason": str(data.get("failedreason"))[:120]})
            raise AppError("GATEWAY_REJECTED", status_code=502)
        return str(url)

    @staticmethod
    def _from_validation(data: dict[str, Any]) -> Validation:
        raw_status = str(data.get("status", "")).upper()
        if raw_status in {"VALID", "VALIDATED"}:
            status = "VALID"
        elif raw_status in {"PENDING", "UNATTEMPTED"}:
            status = "PENDING"
        elif raw_status == "CANCELLED":
            status = "CANCELLED"
        else:
            status = "FAILED"
        return Validation(
            status=status,  # type: ignore[arg-type]
            tran_id=data.get("tran_id"),
            amount=to_paisa(data.get("currency_amount") or data.get("amount")),
            currency=data.get("currency_type") or data.get("currency"),
            provider_txn_id=data.get("bank_tran_id") or data.get("val_id"),
            method_hint=data.get("card_issuer") or data.get("card_type"),
            reason=data.get("error") or data.get("failedreason"),
            raw={k: v for k, v in data.items() if "pass" not in k.lower()},
        )

    def validate(self, payload: dict[str, str]) -> Validation:
        val_id = payload.get("val_id")
        if not val_id:
            return Validation(status="FAILED", tran_id=payload.get("tran_id"), reason="NO_VAL_ID", raw=dict(payload))
        return self._from_validation(self._get(_VALIDATION_PATH, {"val_id": val_id}))

    def query(self, payment: Payment, db: Session) -> Validation:
        data = self._get(_MERCHANT_PATH, {"tran_id": payment.gateway_tran_id or ""})
        elements = data.get("element") or []
        if not elements:
            return Validation(status="PENDING", tran_id=payment.gateway_tran_id, raw=data)
        parsed = [self._from_validation(el) for el in elements]
        return next((v for v in parsed if v.status == "VALID"), parsed[0])

    def refund(self, payment: Payment, amount: int, reason: str, ref_id: str) -> RefundResult:
        data = self._get(
            _MERCHANT_PATH,
            {
                "bank_tran_id": payment.provider_txn_id or "",
                "refund_amount": to_taka(amount),
                "refund_remarks": reason[:200],
                "refund_ref_id": ref_id,
            },
        )
        ok = str(data.get("status", "")).lower() in {"success", "processing"}
        return RefundResult(ok=ok, ref_id=str(data.get("refund_ref_id") or ref_id), reason=data.get("errorReason"))
