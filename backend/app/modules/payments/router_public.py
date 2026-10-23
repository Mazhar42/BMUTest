"""Public payment endpoints: gateway IPN and browser callbacks, the mock gateway page, and the client config.
The browser callbacks only redirect — they never mark anything paid (ROADMAP §9)."""

from __future__ import annotations

import html

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, PlainTextResponse, RedirectResponse

from app.config import get_settings
from app.core import codes
from app.core.errors import NotFound
from app.deps import DB
from app.modules.orders.models import LabOrder
from app.modules.payments import schemas, service
from app.modules.payments.adapters import online_payments_enabled

router = APIRouter(prefix="/public/payments", tags=["public-payments"])


def _result_url(tran_id: str) -> str:
    return f"{get_settings().public_base_url.rstrip('/')}/pay/result?tran={tran_id}"


@router.get("/config", response_model=schemas.PublicConfig)
def config() -> schemas.PublicConfig:
    s = get_settings()
    enabled = online_payments_enabled()
    return schemas.PublicConfig(
        online_payments=enabled,
        provider=s.payment_provider,
        methods=["bkash", "nagad", "upay", "rocket", "card"] if enabled else [],
    )


async def _form(request: Request) -> dict[str, str]:
    data = await request.form()
    return {k: str(v) for k, v in data.items()}


@router.post("/sslcommerz/ipn", response_class=PlainTextResponse)
async def sslcommerz_ipn(request: Request, db: DB) -> str:
    """Server-to-server notification. We call the Validation API with val_id before believing anything."""
    s = get_settings()
    if s.payment_provider != "sslcommerz":
        raise NotFound("payment")
    service.process_ipn(db, await _form(request))
    db.commit()
    return "OK"


@router.api_route("/sslcommerz/{outcome}", methods=["GET", "POST"], include_in_schema=False)
async def sslcommerz_return(outcome: str, request: Request) -> RedirectResponse:
    if outcome not in {"success", "fail", "cancel"}:
        raise NotFound("payment")
    form = await _form(request) if request.method == "POST" else dict(request.query_params)
    return RedirectResponse(_result_url(form.get("tran_id", "")), status_code=303)


# ---- mock gateway (dev / tests / E2E; 404 in prod) -------------------------------------------------

_PAGE = """<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Mock payment gateway</title><style>
body{{font-family:system-ui,sans-serif;background:#faf8f3;margin:0;display:grid;place-items:center;min-height:100vh}}
main{{background:#fff;border-radius:20px;padding:28px;max-width:380px;width:calc(100% - 32px);box-shadow:0 8px 30px rgba(0,0,0,.12)}}
h1{{font-size:18px;margin:0 0 4px}}p{{color:#6c614f;margin:0 0 18px;font-size:14px}}.amt{{font-size:34px;font-weight:800;margin:6px 0 18px}}
button{{display:block;width:100%;padding:14px;border-radius:12px;border:0;font-size:16px;font-weight:700;margin-top:10px;cursor:pointer}}
.ok{{background:#006a4e;color:#fff}}.no{{background:#fbd5da;color:#9d1f30}}.cn{{background:#f1ede4;color:#39332b}}
small{{display:block;margin-top:16px;color:#8a7d66;text-align:center}}</style></head><body><main>
<h1>Mock payment gateway</h1><p>Order {code} · {method}</p><div class="amt">৳{amount}</div>
<form method="post" action="{base}/{tran}/success"><button class="ok" id="pay-success">Pay now</button></form>
<form method="post" action="{base}/{tran}/fail"><button class="no" id="pay-fail">Simulate failure</button></form>
<form method="post" action="{base}/{tran}/cancel"><button class="cn" id="pay-cancel">Cancel</button></form>
<small>Development only — no money moves.</small></main></body></html>"""


def _mock_enabled() -> None:
    s = get_settings()
    if s.env == "prod" or s.payment_provider != "mock":
        raise NotFound("payment")


@router.get("/mock/{tran_id}", response_class=HTMLResponse)
def mock_page(tran_id: str, db: DB) -> HTMLResponse:
    _mock_enabled()
    payment = service.by_tran_id(db, tran_id)
    order = db.get(LabOrder, payment.order_id)
    amount = (
        f"{payment.amount / 100:,.2f}".rstrip("0").rstrip(".")
        if payment.amount % 100 == 0
        else f"{payment.amount / 100:,.2f}"
    )
    return HTMLResponse(
        _PAGE.format(
            code=html.escape(codes.format_order_code(order.order_code) if order and order.order_code else ""),
            method=html.escape(payment.method_hint or "card"),
            amount=amount,
            base="/api/v1/public/payments/mock",
            tran=html.escape(tran_id),
        )
    )


@router.post("/mock/{tran_id}/{outcome}", include_in_schema=False)
def mock_outcome(tran_id: str, outcome: str, db: DB) -> RedirectResponse:
    _mock_enabled()
    service.mock_complete(db, tran_id, outcome)
    db.commit()
    return RedirectResponse(_result_url(tran_id), status_code=303)
