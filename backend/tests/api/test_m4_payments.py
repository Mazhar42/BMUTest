"""M4 acceptance: teller / counter receipts, gateway (mock + SSLCommerz adapter), IPN idempotency and
amount checks, concurrency, refunds, expiry, reconciliation, day-close."""

from __future__ import annotations

import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.core import clock, codes, settings_store
from app.core.actor import SYSTEM, Actor
from app.core.errors import AppError, Conflict
from app.core.models import AuditLog
from app.db import session_factory
from app.modules.catalog.models import LabTest
from app.modules.identity.permissions import Role
from app.modules.notifications.models import Notification
from app.modules.orders import schemas as order_schemas
from app.modules.orders import service as orders
from app.modules.orders.models import LabOrder, OrderStatus
from app.modules.patients import schemas as patient_schemas
from app.modules.patients import service as patients
from app.modules.patients.models import Channel
from app.modules.payments import service
from app.modules.payments.adapters.base import Customer
from app.modules.payments.adapters.sslcommerz import SslCommerzProvider
from app.modules.payments.models import Payment, PaymentMethod, PaymentStatus, Refund
from app.modules.queue.models import QueueToken, TokenStatus
from tests.api.test_m3_orders import _submit, _submit_helpdesk
from tests.conftest import patient_login

S = "/api/v1/staff"
P = "/api/v1/patient"
PUB = "/api/v1/public/payments"


def _payments(db: Session, order_id: str) -> list[Payment]:
    return list(db.scalars(select(Payment).where(Payment.order_id == order_id).order_by(Payment.created_at)))


def _order(db: Session, order_id: str) -> LabOrder:
    db.flush()
    db.expire_all()
    o = db.get(LabOrder, uuid.UUID(order_id))
    assert o is not None
    return o


def _walkin(
    client: TestClient, staff_headers: Any, catalog: dict[str, Any], *tests: str, **extra: Any
) -> dict[str, Any]:
    return _submit_helpdesk(client, staff_headers, catalog, *(tests or ("CBC", "CREAT")), **extra)


def _ipn(client: TestClient, tran_id: str, amount: str, status: str = "VALID", val_id: str | None = None) -> Any:
    return client.post(
        f"{PUB}/sslcommerz/ipn",
        data={
            "tran_id": tran_id,
            "val_id": val_id or f"val-{uuid.uuid4().hex[:10]}",
            "status": status,
            "amount": amount,
        },
    )


@pytest.fixture
def mock_gateway(monkeypatch: pytest.MonkeyPatch) -> None:
    """Production-style routing (`payment_provider=sslcommerz`, so the IPN route is open) with the mock
    provider's echo standing in for the Validation API."""
    from app.modules.payments import service as svc
    from app.modules.payments.adapters.mock import MockProvider

    monkeypatch.setattr(get_settings(), "payment_provider", "sslcommerz")
    monkeypatch.setattr(get_settings(), "sslcommerz_store_id", "teststore")
    monkeypatch.setattr(get_settings(), "sslcommerz_store_password", "secret")
    monkeypatch.setattr(svc, "get_provider", lambda name=None: MockProvider())


# ---- bank teller ------------------------------------------------------------------------------------


def test_teller_receives_and_token_is_issued(
    client: TestClient, db: Session, catalog: dict[str, Any], staff_headers: Any
) -> None:
    order = _walkin(client, staff_headers, catalog)
    code = codes.format_order_code(order["order_code"])
    teller = staff_headers(Role.BANK_TELLER)

    lk = client.get(f"{S}/payments/lookup/{code}", headers=teller).json()
    assert lk["state"] == "RECEIVABLE" and lk["amount_due"] == 70000 and lk["patient_name"].startswith("Walkin")
    assert lk["token"] is None

    r = client.post(f"{S}/payments/receive/{order['order_code']}", json={"receipt_no": "BK-7781"}, headers=teller)
    assert r.status_code == 200, r.text
    receipt = r.json()
    assert receipt["amount"] == 70000 and receipt["token"]["label"] == "W-001" and receipt["receipt_no"] == "BK-7781"

    assert _order(db, order["id"]).status == OrderStatus.PAID
    sms = db.scalars(select(Notification).where(Notification.template_key == "payment_received_token")).one()
    assert "W-001" in sms.body

    # the second teller sees ALREADY PAID, with who/when/token, and cannot receive again
    again = client.get(f"{S}/payments/lookup/{code}", headers=teller).json()
    assert again["state"] == "ALREADY_PAID" and again["token"]["label"] == "W-001" and again["paid"]["amount"] == 70000
    r = client.post(f"{S}/payments/receive/{code}", json={}, headers=teller)
    assert r.status_code == 409 and r.json()["code"] == "ORDER_ALREADY_PAID" and r.json()["params"]["token"] == "W-001"
    assert len([p for p in _payments(db, order["id"]) if p.status == PaymentStatus.SUCCESS]) == 1

    # the next patient gets the next token number
    second = _walkin(client, staff_headers, catalog, "BG")
    r = client.post(f"{S}/payments/receive/{second['order_code']}", json={}, headers=teller)
    assert r.json()["token"]["label"] == "W-002"


def test_teller_screen_states(client: TestClient, db: Session, catalog: dict[str, Any], staff_headers: Any) -> None:
    teller = staff_headers(Role.BANK_TELLER)
    # NOT VERIFIED YET: an online request waiting for staff
    patient = patient_login(client)
    online = _submit(client, patient, catalog, "CBC")
    lk = client.get(f"{S}/payments/lookup/{online['order_code']}", headers=teller).json()
    assert lk["state"] == "NOT_VERIFIED" and lk["amount_due"] == 0
    r = client.post(f"{S}/payments/receive/{online['order_code']}", json={}, headers=teller)
    assert r.status_code == 409 and r.json()["code"] == "ORDER_NOT_VERIFIED"

    # EXPIRED
    stale = _walkin(client, staff_headers, catalog, "BG")
    with clock.frozen(clock.now() + timedelta(days=8)):
        assert orders.expire_unpaid(db) >= 1
        db.flush()
    assert client.get(f"{S}/payments/lookup/{stale['order_code']}", headers=teller).json()["state"] == "EXPIRED"

    # CLOSED (cancelled) and a mistyped code
    gone = _walkin(client, staff_headers, catalog, "BG")
    client.post(f"{S}/orders/{gone['id']}/cancel", json={"reason": "patient left"}, headers=gone["_headers"])
    assert client.get(f"{S}/payments/lookup/{gone['order_code']}", headers=teller).json()["state"] == "CLOSED"
    bad = gone["order_code"][:-1] + str((int(gone["order_code"][-1]) + 3) % 10)
    r = client.get(f"{S}/payments/lookup/{bad}", headers=teller)
    assert r.status_code == 422 and r.json()["code"] == "CODE_MISTYPED"
    assert client.get(f"{S}/payments/lookup/260101000019", headers=teller).status_code in (404, 422)


def test_receipt_number_and_emergency_priority(
    client: TestClient, db: Session, catalog: dict[str, Any], staff_headers: Any
) -> None:
    settings_store.put(db, "teller_require_receipt_no", True, SYSTEM)
    teller = staff_headers(Role.BANK_TELLER)
    order = _walkin(client, staff_headers, catalog, "BG", priority="EMERGENCY")
    r = client.post(f"{S}/payments/receive/{order['order_code']}", json={}, headers=teller)
    assert r.status_code == 422 and r.json()["code"] == "RECEIPT_NO_REQUIRED"
    r = client.post(f"{S}/payments/receive/{order['order_code']}", json={"receipt_no": "R-1"}, headers=teller)
    assert r.json()["token"]["label"].startswith("P-")


def test_counter_cash_needs_the_setting_and_the_role(
    client: TestClient, db: Session, catalog: dict[str, Any], staff_headers: Any
) -> None:
    cashier = staff_headers(Role.CASHIER)
    order = _walkin(client, staff_headers, catalog, "BG")
    body = {"method": "COUNTER_CASH"}
    r = client.post(f"{S}/payments/receive/{order['order_code']}", json=body, headers=cashier)
    assert r.status_code == 403 and r.json()["code"] == "COUNTER_PAYMENT_DISABLED"
    settings_store.put(db, "counter_payment_enabled", True, SYSTEM)
    r = client.post(f"{S}/payments/receive/{order['order_code']}", json=body, headers=cashier)
    assert r.status_code == 200 and r.json()["method"] == "COUNTER_CASH"
    # a teller may not use the counter method, a cashier may not use the bank method
    other = _walkin(client, staff_headers, catalog, "BG")
    assert (
        client.post(
            f"{S}/payments/receive/{other['order_code']}", json=body, headers=staff_headers(Role.BANK_TELLER)
        ).status_code
        == 403
    )
    assert client.post(f"{S}/payments/receive/{other['order_code']}", json={}, headers=cashier).status_code == 403


def test_waiver_then_teller_collects_only_the_remainder(
    client: TestClient, db: Session, catalog: dict[str, Any], staff_headers: Any
) -> None:
    order = _walkin(client, staff_headers, catalog, "LIPID", fee_category="CONCESSION", waiver_reason="Staff family")
    wid = order["waivers"][0]["id"]
    client.post(
        f"{S}/waivers/{wid}/decision",
        json={"approve": True, "discount": 40000, "reason": "Half price"},
        headers=staff_headers(Role.WAIVER_APPROVER),
    )
    teller = staff_headers(Role.BANK_TELLER)
    lk = client.get(f"{S}/payments/lookup/{order['order_code']}", headers=teller).json()
    assert lk["total"] == 60000 and lk["discount"] == 40000 and lk["amount_due"] == 60000
    r = client.post(f"{S}/payments/receive/{order['order_code']}", json={}, headers=teller)
    assert r.json()["amount"] == 60000


def test_day_close_totals_equal_the_sum_of_payments(
    client: TestClient, db: Session, catalog: dict[str, Any], staff_headers: Any
) -> None:
    t1, t2 = staff_headers(Role.BANK_TELLER), staff_headers(Role.BANK_TELLER)
    amounts = {}
    for headers, tests in ((t1, ("CBC",)), (t1, ("CREAT", "BG")), (t2, ("HBA1C",))):
        o = _walkin(client, staff_headers, catalog, *tests)
        r = client.post(f"{S}/payments/receive/{o['order_code']}", json={}, headers=headers)
        amounts.setdefault(id(headers), []).append(r.json()["amount"])
    for headers in (t1, t2):
        dc = client.get(f"{S}/payments/day-close", headers=headers).json()
        assert dc["count"] == len(amounts[id(headers)])
        assert dc["total"] == sum(amounts[id(headers)]) == sum(r["amount"] for r in dc["rows"])
        assert dc["net"] == dc["total"] and dc["refunded_total"] == 0
    # yesterday is empty; a teller can't read another teller's close
    assert (
        client.get(
            f"{S}/payments/day-close", params={"day": str(clock.today() - timedelta(days=1))}, headers=t1
        ).json()["count"]
        == 0
    )
    other_id = client.get(f"{S}/payments/day-close", headers=t2).json()["staff_id"]
    assert client.get(f"{S}/payments/day-close", params={"staff_id": other_id}, headers=t1).status_code == 403
    admin = staff_headers((Role.LAB_ADMIN, None))
    assert client.get(f"{S}/payments/day-close", params={"staff_id": other_id}, headers=admin).json()["count"] == 1


def test_token_pdf_requires_permission(client: TestClient, catalog: dict[str, Any], staff_headers: Any) -> None:
    o = _walkin(client, staff_headers, catalog, "BG")
    teller = staff_headers(Role.BANK_TELLER)
    token_id = client.post(f"{S}/payments/receive/{o['order_code']}", json={}, headers=teller).json()["token"]["id"]
    assert client.post(f"{S}/tokens/{token_id}/print", headers=staff_headers(Role.VERIFIER)).status_code == 403


# ---- gateway / IPN ----------------------------------------------------------------------------------


def _online_ready(
    client: TestClient, catalog: dict[str, Any], staff_headers: Any
) -> tuple[dict[str, str], dict[str, Any]]:
    patient = patient_login(client)
    order = _submit(client, patient, catalog, "CBC", "CREAT")
    client.post(f"{S}/orders/{order['id']}/verify", json={}, headers=staff_headers(Role.VERIFIER))
    return patient, order


def test_online_payment_with_mock_gateway(
    client: TestClient, db: Session, catalog: dict[str, Any], staff_headers: Any
) -> None:
    patient, order = _online_ready(client, catalog, staff_headers)
    assert client.get(f"{PUB}/config").json()["online_payments"] is True
    r = client.post(f"{P}/orders/{order['id']}/pay", json={"method": "bkash"}, headers=patient)
    assert r.status_code == 200, r.text
    pay = r.json()
    assert pay["amount"] == 70000 and f"/payments/mock/{pay['tran_id']}" in pay["redirect_url"]
    assert client.get(f"{P}/payments/{pay['tran_id']}", headers=patient).json()["status"] == "PENDING"
    assert "৳700" in client.get(f"{PUB}/mock/{pay['tran_id']}").text

    done = client.post(f"{PUB}/mock/{pay['tran_id']}/success", follow_redirects=False)
    assert done.status_code == 303 and f"/pay/result?tran={pay['tran_id']}" in done.headers["location"]
    st = client.get(f"{P}/payments/{pay['tran_id']}", headers=patient).json()
    assert st["status"] == "SUCCESS" and st["order_status"] == "PAID"
    assert _order(db, order["id"]).status == OrderStatus.PAID
    assert db.scalars(select(Notification).where(Notification.template_key == "payment_received")).one()
    # PAID: nothing left to pay online
    assert client.post(f"{P}/orders/{order['id']}/pay", json={"method": "card"}, headers=patient).status_code == 409


def test_failed_cancelled_and_retry(
    client: TestClient, db: Session, catalog: dict[str, Any], staff_headers: Any
) -> None:
    patient, order = _online_ready(client, catalog, staff_headers)
    first = client.post(f"{P}/orders/{order['id']}/pay", json={"method": "card"}, headers=patient).json()
    client.post(f"{PUB}/mock/{first['tran_id']}/fail")
    assert client.get(f"{P}/payments/{first['tran_id']}", headers=patient).json()["status"] == "FAILED"
    assert _order(db, order["id"]).status == OrderStatus.AWAITING_PAYMENT
    second = client.post(f"{P}/orders/{order['id']}/pay", json={"method": "nagad"}, headers=patient).json()
    third = client.post(f"{P}/orders/{order['id']}/pay", json={"method": "upay"}, headers=patient).json()
    assert client.get(f"{P}/payments/{second['tran_id']}", headers=patient).json()["status"] == "CANCELLED"  # replaced
    client.post(f"{PUB}/mock/{third['tran_id']}/cancel")
    assert client.get(f"{P}/payments/{third['tran_id']}", headers=patient).json()["status"] == "CANCELLED"


def test_payment_status_is_private(client: TestClient, catalog: dict[str, Any], staff_headers: Any) -> None:
    patient, order = _online_ready(client, catalog, staff_headers)
    pay = client.post(f"{P}/orders/{order['id']}/pay", json={"method": "bkash"}, headers=patient).json()
    other = patient_login(client, "01655555555")
    assert client.get(f"{P}/payments/{pay['tran_id']}", headers=other).status_code == 404
    assert client.post(f"{P}/orders/{order['id']}/pay", json={"method": "bkash"}, headers=other).status_code == 404


def test_duplicate_ipn_gives_one_success_and_one_audit_trail(
    client: TestClient, db: Session, catalog: dict[str, Any], staff_headers: Any, mock_gateway: None
) -> None:
    patient, order = _online_ready(client, catalog, staff_headers)
    pay = client.post(f"{P}/orders/{order['id']}/pay", json={"method": "bkash"}, headers=patient)
    assert pay.status_code == 200, pay.text
    tran = pay.json()["tran_id"]
    for _ in range(3):
        assert _ipn(client, tran, "700.00", val_id="val-same-1").text == "OK"
    payments = _payments(db, order["id"])
    assert [p.status for p in payments] == [PaymentStatus.SUCCESS]
    actions = [a.action for a in db.scalars(select(AuditLog).where(AuditLog.entity_id == str(payments[0].id)))]
    assert actions.count("payment.SUCCESS") == 1
    assert _order(db, order["id"]).status == OrderStatus.PAID
    assert not db.scalars(select(Refund)).all()  # a repeated callback is not a duplicate payment


def test_ipn_with_wrong_amount_is_flagged_failed(
    client: TestClient, db: Session, catalog: dict[str, Any], staff_headers: Any, mock_gateway: None
) -> None:
    patient, order = _online_ready(client, catalog, staff_headers)
    tran = client.post(f"{P}/orders/{order['id']}/pay", json={"method": "card"}, headers=patient).json()["tran_id"]
    _ipn(client, tran, "1.00")
    p = _payments(db, order["id"])[0]
    assert p.status == PaymentStatus.FAILED and p.status_reason == "AMOUNT_MISMATCH"
    assert _order(db, order["id"]).status == OrderStatus.AWAITING_PAYMENT  # the order is not paid


def test_ipn_unknown_transaction_and_wrong_tran_id(client: TestClient, db: Session, mock_gateway: None) -> None:
    assert _ipn(client, "BMUDOESNOTEXIST", "10.00").text == "OK"
    from app.modules.payments.models import PaymentEvent

    assert db.scalars(select(PaymentEvent).where(PaymentEvent.kind == "ipn_unknown_tran")).first() is not None


def test_late_gateway_success_after_in_person_payment_raises_a_refund(
    client: TestClient, db: Session, catalog: dict[str, Any], staff_headers: Any, mock_gateway: None
) -> None:
    patient, order = _online_ready(client, catalog, staff_headers)
    tran = client.post(f"{P}/orders/{order['id']}/pay", json={"method": "bkash"}, headers=patient).json()["tran_id"]
    client.post(f"{S}/payments/receive/{order['order_code']}", json={}, headers=staff_headers(Role.BANK_TELLER))
    assert _payments(db, order["id"])[0].status == PaymentStatus.CANCELLED  # gateway attempt cancelled by the teller
    # the patient had already paid on their phone: the gateway confirms late
    _ipn(client, tran, "700.00")
    db.expire_all()
    gateway = db.scalars(select(Payment).where(Payment.gateway_tran_id == tran)).one()
    refund = db.scalars(select(Refund)).one()
    assert gateway.status == PaymentStatus.REFUND_PENDING
    assert refund.requested_by is None and refund.reason == "DUPLICATE_PAYMENT" and refund.amount == 70000
    assert _order(db, order["id"]).status == OrderStatus.PAID  # the order stays paid


def test_requery_job_settles_a_payment_whose_ipn_never_arrived(
    client: TestClient, db: Session, catalog: dict[str, Any], staff_headers: Any
) -> None:
    patient, order = _online_ready(client, catalog, staff_headers)
    pay = client.post(f"{P}/orders/{order['id']}/pay", json={"method": "bkash"}, headers=patient).json()
    p = _payments(db, order["id"])[0]
    assert service.pending_to_requery(db) == []
    with clock.frozen(clock.now() + timedelta(minutes=11)):
        assert service.pending_to_requery(db) == [p.id]
    # the patient paid on the mock page (outcome stored) but the settlement call was lost
    from app.modules.payments.models import PaymentEvent

    service.add_event(
        db, p.id, "mock_result", {"tran_id": pay["tran_id"], "val_id": "v-late", "status": "VALID", "amount": "700.00"}
    )
    db.flush()
    assert service.requery(db, p.id).status == PaymentStatus.SUCCESS
    assert _order(db, order["id"]).status == OrderStatus.PAID
    assert db.scalars(select(func.count()).select_from(PaymentEvent)).one() >= 2


def test_stale_pending_payments_expire(
    client: TestClient, db: Session, catalog: dict[str, Any], staff_headers: Any
) -> None:
    patient, order = _online_ready(client, catalog, staff_headers)
    client.post(f"{P}/orders/{order['id']}/pay", json={"method": "bkash"}, headers=patient)
    with clock.frozen(clock.now() + timedelta(hours=25)):
        assert service.expire_stale(db) == 1
    assert _payments(db, order["id"])[0].status == PaymentStatus.EXPIRED


def test_mock_gateway_is_off_in_production(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(get_settings(), "env", "prod")
    assert client.get(f"{PUB}/config").json()["online_payments"] is False
    assert client.get(f"{PUB}/mock/BMUANY").status_code == 404
    assert client.post(f"{PUB}/mock/BMUANY/success").status_code == 404


# ---- SSLCommerz adapter (HTTP mocked) ---------------------------------------------------------------


def _ssl(handler: Any) -> SslCommerzProvider:
    return SslCommerzProvider(httpx.Client(transport=httpx.MockTransport(handler)))


@pytest.fixture
def ssl_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(get_settings(), "sslcommerz_store_id", "teststore")
    monkeypatch.setattr(get_settings(), "sslcommerz_store_password", "secret")
    monkeypatch.setattr(get_settings(), "sslcommerz_sandbox", True)


def test_sslcommerz_initiate_validate_query_refund(ssl_settings: None) -> None:
    seen: list[httpx.Request] = []

    def handler(req: httpx.Request) -> httpx.Response:
        seen.append(req)
        path = req.url.path
        if path.endswith("gwprocess/v4/api.php"):
            return httpx.Response(200, json={"status": "SUCCESS", "GatewayPageURL": "https://pay.example/session/1"})
        if path.endswith("validationserverAPI.php"):
            return httpx.Response(
                200,
                json={
                    "status": "VALID",
                    "tran_id": "BMUX",
                    "amount": "700.00",
                    "currency_type": "BDT",
                    "bank_tran_id": "BANK1",
                    "card_type": "BKASH-BKash",
                },
            )
        if "refund_amount" in str(req.url):
            return httpx.Response(200, json={"status": "success", "refund_ref_id": "RF1"})
        return httpx.Response(
            200,
            json={
                "element": [
                    {
                        "status": "VALID",
                        "tran_id": "BMUX",
                        "amount": "700.00",
                        "currency": "BDT",
                        "bank_tran_id": "BANK1",
                    }
                ]
            },
        )

    provider = _ssl(handler)
    payment = Payment(
        id=uuid.uuid4(),
        gateway_tran_id="BMUX",
        amount=70000,
        method=PaymentMethod.GATEWAY,
        method_hint="bkash",
        provider_txn_id="BANK1",
    )
    url = provider.initiate(payment, "261008000013", Customer("Rahima", "+8801712345678"))
    assert url == "https://pay.example/session/1"
    form = seen[0].content.decode()
    assert (
        "total_amount=700.00" in form
        and "currency=BDT" in form
        and "tran_id=BMUX" in form
        and "multi_card_name=bkash" in form
    )
    assert "sandbox.sslcommerz.com" in str(seen[0].url)

    v = provider.validate({"tran_id": "BMUX", "val_id": "V1", "status": "VALID"})
    assert (v.status, v.amount, v.currency, v.provider_txn_id) == ("VALID", 70000, "BDT", "BANK1")
    assert provider.validate({"tran_id": "BMUX"}).status == "FAILED"  # no val_id → never trusted
    q = provider.query(payment, None)  # type: ignore[arg-type]
    assert q.status == "VALID" and q.amount == 70000
    assert provider.refund(payment, 70000, "duplicate", "ref-1").ok


def test_sslcommerz_errors_and_missing_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    payment = Payment(id=uuid.uuid4(), gateway_tran_id="BMUX", amount=100, method=PaymentMethod.GATEWAY)
    monkeypatch.setattr(get_settings(), "sslcommerz_store_id", "")
    with pytest.raises(AppError) as e:
        _ssl(lambda r: httpx.Response(200, json={})).initiate(payment, "1", Customer("A", None))
    assert e.value.code == "GATEWAY_NOT_CONFIGURED"
    monkeypatch.setattr(get_settings(), "sslcommerz_store_id", "s")
    monkeypatch.setattr(get_settings(), "sslcommerz_store_password", "p")
    with pytest.raises(AppError) as e:
        _ssl(lambda r: httpx.Response(200, json={"status": "FAILED", "failedreason": "bad"})).initiate(
            payment, "1", Customer("A", None)
        )
    assert e.value.code == "GATEWAY_REJECTED"
    with pytest.raises(AppError) as e:
        _ssl(lambda r: httpx.Response(500)).validate({"val_id": "v"})
    assert e.value.code == "GATEWAY_UNAVAILABLE"


def test_ipn_route_verifies_with_the_gateway_never_the_payload(
    client: TestClient,
    db: Session,
    catalog: dict[str, Any],
    staff_headers: Any,
    ssl_settings: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(get_settings(), "payment_provider", "sslcommerz")
    patient, order = _online_ready(client, catalog, staff_headers)

    def real_gateway(req: httpx.Request) -> httpx.Response:
        if req.url.path.endswith("gwprocess/v4/api.php"):
            return httpx.Response(200, json={"status": "SUCCESS", "GatewayPageURL": "https://pay.example/s"})
        # the gateway says: this val_id was for 1.00 BDT
        return httpx.Response(
            200,
            json={
                "status": "VALID",
                "tran_id": tran_box[0],
                "amount": "1.00",
                "currency_type": "BDT",
                "bank_tran_id": "B9",
            },
        )

    tran_box: list[str] = [""]
    from app.modules.payments import service as svc

    monkeypatch.setattr(svc, "get_provider", lambda name=None: _ssl(real_gateway))
    pay = client.post(f"{P}/orders/{order['id']}/pay", json={"method": "card"}, headers=patient).json()
    tran_box[0] = pay["tran_id"]
    assert pay["redirect_url"] == "https://pay.example/s"
    # the IPN CLAIMS the full amount, the Validation API says 1.00 → rejected
    _ipn(client, pay["tran_id"], "700.00", val_id="V-claim")
    p = _payments(db, order["id"])[0]
    assert p.status == PaymentStatus.FAILED and p.status_reason == "AMOUNT_MISMATCH"
    # browser success redirects change nothing
    r = client.post(
        f"{PUB}/sslcommerz/success", data={"tran_id": pay["tran_id"], "status": "VALID"}, follow_redirects=False
    )
    assert r.status_code == 303 and _order(db, order["id"]).status == OrderStatus.AWAITING_PAYMENT


# ---- refunds ---------------------------------------------------------------------------------------


def _paid_at_bank(
    client: TestClient, staff_headers: Any, catalog: dict[str, Any]
) -> tuple[dict[str, Any], dict[str, Any]]:
    order = _walkin(client, staff_headers, catalog, "CBC")
    r = client.post(
        f"{S}/payments/receive/{order['order_code']}",
        json={"receipt_no": "RB"},
        headers=staff_headers(Role.BANK_TELLER),
    )
    return order, r.json()


def test_manual_refund_two_person_rule(
    client: TestClient, db: Session, catalog: dict[str, Any], staff_headers: Any
) -> None:
    order, receipt = _paid_at_bank(client, staff_headers, catalog)
    cashier = staff_headers(Role.CASHIER)
    admin = staff_headers((Role.LAB_ADMIN, None))
    r = client.post(f"{S}/payments/{receipt['payment_id']}/refund", json={"reason": "Patient left"}, headers=cashier)
    assert r.status_code == 201, r.text
    refund_id = r.json()["id"]
    assert _order(db, order["id"]).status == OrderStatus.REFUND_PENDING
    assert (
        client.post(
            f"{S}/payments/{receipt['payment_id']}/refund", json={"reason": "again"}, headers=cashier
        ).status_code
        == 409
    )
    # the teller role can't approve; the requester can't approve their own request
    assert (
        client.post(
            f"{S}/refunds/{refund_id}/approve", json={"mode": "MANUAL", "manual_reference": "x"}, headers=cashier
        ).status_code
        == 403
    )
    # a reference is needed for a manual refund
    r = client.post(f"{S}/refunds/{refund_id}/approve", json={"mode": "MANUAL"}, headers=admin)
    assert r.json()["code"] == "REFUND_REFERENCE_REQUIRED"
    r = client.post(
        f"{S}/refunds/{refund_id}/approve",
        json={"mode": "MANUAL", "manual_reference": "Cash voucher 55"},
        headers=admin,
    )
    assert r.status_code == 200 and r.json()["status"] == "COMPLETED"
    db.expire_all()
    assert _order(db, order["id"]).status == OrderStatus.REFUNDED
    assert db.scalars(select(Payment).where(Payment.order_id == order["id"])).one().status == PaymentStatus.REFUNDED
    token = db.scalars(select(QueueToken).where(QueueToken.order_id == order["id"])).one()
    assert token.status == TokenStatus.CANCELLED
    assert db.scalars(select(Notification).where(Notification.template_key == "refund_completed")).one()
    assert (
        client.post(
            f"{S}/refunds/{refund_id}/approve", json={"mode": "MANUAL", "manual_reference": "y"}, headers=admin
        ).status_code
        == 409
    )
    # the teller's day-close shows it as refunded
    teller_id = client.get(f"{S}/payments/by-order/{order['order_code']}", headers=admin).json()["payments"][0][
        "received_by_staff_id"
    ]
    dc = client.get(f"{S}/payments/day-close", params={"staff_id": teller_id}, headers=admin).json()
    assert dc["refunded_total"] == 40000 and dc["net"] == 0


def test_refund_rejected_restores_the_payment(
    client: TestClient, db: Session, catalog: dict[str, Any], staff_headers: Any
) -> None:
    order, receipt = _paid_at_bank(client, staff_headers, catalog)
    rid = client.post(
        f"{S}/payments/{receipt['payment_id']}/refund", json={"reason": "Mistake"}, headers=staff_headers(Role.CASHIER)
    ).json()["id"]
    admin = staff_headers((Role.LAB_ADMIN, None))
    r = client.post(f"{S}/refunds/{rid}/reject", json={"reason": "Sample was taken"}, headers=admin)
    assert r.json()["status"] == "REJECTED"
    assert _order(db, order["id"]).status == OrderStatus.PAID
    assert db.scalars(select(Payment).where(Payment.order_id == order["id"])).one().status == PaymentStatus.SUCCESS


def test_provider_refund_for_gateway_payment(
    client: TestClient, db: Session, catalog: dict[str, Any], staff_headers: Any
) -> None:
    patient, order = _online_ready(client, catalog, staff_headers)
    tran = client.post(f"{P}/orders/{order['id']}/pay", json={"method": "bkash"}, headers=patient).json()["tran_id"]
    client.post(f"{PUB}/mock/{tran}/success")
    pid = _payments(db, order["id"])[0].id
    rid = client.post(
        f"{S}/payments/{pid}/refund", json={"reason": "Duplicate test"}, headers=staff_headers(Role.CASHIER)
    ).json()["id"]
    admin = staff_headers((Role.LAB_ADMIN, None))
    assert (
        client.post(f"{S}/refunds/{rid}/approve", json={"mode": "PROVIDER"}, headers=admin).json()["status"]
        == "COMPLETED"
    )
    # a teller payment cannot go through the provider
    _, receipt = _paid_at_bank(client, staff_headers, catalog)
    rid2 = client.post(
        f"{S}/payments/{receipt['payment_id']}/refund", json={"reason": "x y z"}, headers=staff_headers(Role.CASHIER)
    ).json()["id"]
    assert (
        client.post(f"{S}/refunds/{rid2}/approve", json={"mode": "PROVIDER"}, headers=admin).json()["code"]
        == "REFUND_NEEDS_MANUAL_MODE"
    )


def test_refund_permissions_and_listing(client: TestClient, catalog: dict[str, Any], staff_headers: Any) -> None:
    order, receipt = _paid_at_bank(client, staff_headers, catalog)
    assert (
        client.post(
            f"{S}/payments/{receipt['payment_id']}/refund",
            json={"reason": "no way"},
            headers=staff_headers(Role.BANK_TELLER),
        ).status_code
        == 403
    )
    client.post(
        f"{S}/payments/{receipt['payment_id']}/refund",
        json={"reason": "valid reason"},
        headers=staff_headers(Role.CASHIER),
    )
    admin = staff_headers((Role.LAB_ADMIN, None))
    rows = client.get(f"{S}/refunds", headers=admin).json()
    assert rows[0]["order_code"] == order["order_code"] and rows[0]["payment_method"] == "BANK_TELLER"


# ---- concurrency (real parallel sessions) -----------------------------------------------------------


def _committed_walkin() -> tuple[str, str]:
    from app.modules.catalog.seed import seed_catalog

    actor = Actor(type="staff", id=uuid.uuid4(), label="helpdesk", permissions=frozenset({"order.create_walkin"}))
    with session_factory()() as db:
        seed_catalog(db, False)
        db.flush()
        tests = {t.code: t for t in db.scalars(select(LabTest))}
        patient = patients.register_by_staff(
            db,
            patient_schemas.StaffPatientIn(
                full_name="Race Patient", sex="M", age_years=40, mobile="01711999888", force=True
            ),
            actor,
            Channel.HELPDESK,
        )
        order = orders.create_walkin(
            db, order_schemas.WalkinIn(patient_id=patient.id, test_ids=[tests["BG"].id]), actor
        )
        db.commit()
        return str(order.id), order.order_code or ""


@pytest.mark.concurrency
def test_two_tellers_receiving_the_same_code_give_exactly_one_success(committed: None) -> None:
    order_id, code = _committed_walkin()
    n = 6
    barrier = threading.Barrier(n)

    def teller(i: int) -> str:
        actor = Actor(type="staff", id=uuid.uuid4(), label=f"t{i}", permissions=frozenset(), station=f"Booth {i}")
        with session_factory()() as db:
            barrier.wait()
            try:
                service.receive_in_person(db, code, PaymentMethod.BANK_TELLER, actor, f"R{i}")
                db.commit()
                return "ok"
            except Conflict as exc:
                db.rollback()
                return exc.code

    with ThreadPoolExecutor(n) as pool:
        results = list(pool.map(teller, range(n)))
    assert results.count("ok") == 1 and results.count("ORDER_ALREADY_PAID") == n - 1
    with session_factory()() as db:
        pays = list(db.scalars(select(Payment).where(Payment.order_id == uuid.UUID(order_id))))
        assert [p.status for p in pays] == [PaymentStatus.SUCCESS]
        assert len(list(db.scalars(select(QueueToken)))) == 1


@pytest.mark.concurrency
def test_parallel_ipns_settle_once(committed: None, monkeypatch: pytest.MonkeyPatch) -> None:
    order_id, _code = _committed_walkin()
    with session_factory()() as db:
        order = db.get(LabOrder, uuid.UUID(order_id))
        assert order is not None
        pay = service.start_online_payment(db, order, "bkash", SYSTEM)
        db.commit()
        pid, tran = pay.id, pay.gateway_tran_id
    from app.modules.payments.adapters.base import Validation

    v = Validation(status="VALID", tran_id=tran, amount=15000, currency="BDT", provider_txn_id="TX-ONCE", raw={})
    barrier = threading.Barrier(5)

    def ipn(_: int) -> None:
        with session_factory()() as db:
            barrier.wait()
            service.apply_validation(db, pid, v, "ipn")
            db.commit()

    with ThreadPoolExecutor(5) as pool:
        list(pool.map(ipn, range(5)))
    with session_factory()() as db:
        success = db.scalars(
            select(AuditLog).where(AuditLog.entity_id == str(pid), AuditLog.action == "payment.SUCCESS")
        ).all()
        assert len(success) == 1
        assert db.get(Payment, pid).status == PaymentStatus.SUCCESS  # type: ignore[union-attr]
        assert not list(db.scalars(select(Refund)))


# ---- reconciliation --------------------------------------------------------------------------------

BANK_COLUMNS = {
    "bank_name": "Sonali Bank",
    "date_column": "Date",
    "amount_column": "Credit",
    "reference_column": "Narration",
    "receipt_column": "Receipt",
    "date_format": "%d/%m/%Y",
}


def _upload(client: TestClient, headers: dict[str, str], csv_text: str, name: str = "stmt.csv") -> Any:
    return client.post(
        f"{S}/reconciliation/import",
        data=BANK_COLUMNS,
        files={"file": (name, csv_text.encode("utf-8"), "text/csv")},
        headers=headers,
    )


def test_statement_import_matches_and_lists_exceptions(
    client: TestClient, db: Session, catalog: dict[str, Any], staff_headers: Any
) -> None:
    good, _ = _paid_at_bank(client, staff_headers, catalog)  # CBC 400.00
    short, _ = _paid_at_bank(client, staff_headers, catalog)  # CBC 400.00 recorded
    admin = staff_headers((Role.LAB_ADMIN, None))
    today = clock.today().strftime("%d/%m/%Y")
    dashed = codes.format_order_code(good["order_code"])
    csv_text = (
        "Date,Narration,Debit,Credit,Receipt\n"
        f'{today},LAB FEE {dashed} CASH,,"400.00",R-1\n'
        f"{today},LAB FEE {short['order_code']},,350.00,R-2\n"
        f"{today},TRANSFER FROM SOMEONE,,125.00,R-3\n"
        f"{today},OUTGOING,10.00,,\n"
    )
    r = _upload(client, admin, csv_text)
    assert r.status_code == 200, r.text
    body = r.json()
    assert (body["rows"], body["matched"], body["exceptions"], body["skipped"]) == (4, 1, 2, 1)
    exc = client.get(f"{S}/reconciliation/exceptions", headers=admin).json()
    assert {e["match"] for e in exc} == {"AMOUNT_MISMATCH", "UNMATCHED"}
    mismatch = next(e for e in exc if e["match"] == "AMOUNT_MISMATCH")
    assert mismatch["order_code"] == short["order_code"] and "400.00" in mismatch["note"]
    pays = {p.order_id: p.reconciliation_status for p in db.scalars(select(Payment))}
    assert pays[uuid.UUID(good["id"])] == "MATCHED" and pays[uuid.UUID(short["id"])] == "EXCEPTION"

    # re-uploading the same statement changes nothing (lines are fingerprinted)
    again = _upload(client, admin, csv_text).json()
    assert again["matched"] == 0 and again["exceptions"] == 0 and again["skipped"] == 4
    assert len(client.get(f"{S}/reconciliation/exceptions", headers=admin).json()) == 2

    # resolve an exception with a note
    line = exc[0]
    r = client.post(
        f"{S}/reconciliation/lines/{line['id']}/resolve", json={"note": "Donation, not a lab payment"}, headers=admin
    )
    assert r.json()["match"] == "RESOLVED"
    assert len(client.get(f"{S}/reconciliation/exceptions", headers=admin).json()) == 1
    assert client.get(f"{S}/reconciliation/mappings", headers=admin).json()[0]["bank_name"] == "Sonali Bank"


def test_statement_validation_and_permissions(client: TestClient, staff_headers: Any) -> None:
    admin = staff_headers((Role.LAB_ADMIN, None))
    r = _upload(client, admin, "Foo,Bar\n1,2\n")
    assert r.status_code == 422 and r.json()["code"] == "CSV_COLUMNS_MISSING"
    assert _upload(client, staff_headers(Role.BANK_TELLER), "Date,Narration,Credit\n").status_code == 403


def test_late_teller_payment_matches_on_the_nightly_job(
    client: TestClient, db: Session, catalog: dict[str, Any], staff_headers: Any
) -> None:
    from app.modules.payments import reconciliation

    order = _walkin(client, staff_headers, catalog, "CBC")
    admin = staff_headers((Role.LAB_ADMIN, None))
    today = clock.today().strftime("%d/%m/%Y")
    _upload(client, admin, f"Date,Narration,Credit,Receipt\n{today},{order['order_code']},400.00,R9\n")
    assert client.get(f"{S}/reconciliation/exceptions", headers=admin).json()[0]["match"] == "UNMATCHED"
    client.post(
        f"{S}/payments/receive/{order['order_code']}", json={}, headers=staff_headers(Role.BANK_TELLER)
    )  # back-entered
    assert reconciliation.rematch_open_lines(db) == {"checked": 1, "matched": 1}
    assert client.get(f"{S}/reconciliation/exceptions", headers=admin).json() == []
