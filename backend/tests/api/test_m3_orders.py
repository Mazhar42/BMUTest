"""M3 acceptance: online submit → staff verify → patient sees price and preparation; clarification and
rejection; help-desk walk-in with inline verification; waivers; price snapshot; isolation."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core import clock, codes
from app.core.actor import SYSTEM
from app.core.models import AuditLog
from app.modules.catalog import service as catalog_service
from app.modules.identity.permissions import Role
from app.modules.notifications.models import Notification
from app.modules.payments.models import Payment
from tests.conftest import JPEG, PNG, add_self, patient_login

P = "/api/v1/patient"
S = "/api/v1/staff"


def _upload(client: TestClient, headers: dict[str, str], patient_id: str, n: int = 1) -> str:
    files = [("files", (f"p{i}.jpg", JPEG, "image/jpeg")) for i in range(n)]
    r = client.post(
        f"{P}/prescriptions", data={"patient_id": patient_id, "doctor_name": "Dr. Rahman"}, files=files, headers=headers
    )
    assert r.status_code == 201, r.text
    return str(r.json()["id"])


def _submit(client: TestClient, headers: dict[str, str], catalog: dict[str, Any], *tests: str) -> dict[str, Any]:
    pid = add_self(client, headers)
    rx = _upload(client, headers, pid)
    r = client.post(
        f"{P}/orders",
        json={"patient_id": pid, "prescription_id": rx, "test_ids": [str(catalog[c].id) for c in tests]},
        headers=headers,
    )
    assert r.status_code == 201, r.text
    body: dict[str, Any] = r.json()
    return body


def _sms_templates(db: Session, order_id: str) -> list[str]:
    rows = db.scalars(select(Notification).where(Notification.order_id == order_id).order_by(Notification.created_at))
    return [n.template_key for n in rows]


def test_online_submit_verify_patient_sees_price_and_prep(
    client: TestClient, db: Session, catalog: dict[str, Any], staff_headers: Any
) -> None:
    patient = patient_login(client)
    order = _submit(client, patient, catalog, "CBC", "FBS")
    assert order["status"] == "PENDING_VERIFICATION"
    assert codes.parse_order_code(order["order_code"]) == order["order_code"]
    assert order["order_code"].startswith(clock.today().strftime("%y%m%d"))
    assert order["sla_due_at"] is not None
    assert order["total"] == 40000 + 15000
    assert [s["state"] for s in order["timeline"]][:2] == ["done", "current"]

    verifier = staff_headers(Role.VERIFIER)
    queue = client.get(f"{S}/verification/queue", headers=verifier).json()
    assert order["id"] in [row["id"] for row in queue]
    detail = client.get(f"{S}/orders/{order['order_code']}", headers=verifier).json()
    rx_id = detail["prescription"]["id"]
    img = client.get(f"{S}/prescriptions/{rx_id}/images/1", headers=verifier)
    assert img.status_code == 200 and img.headers["content-type"] == "image/jpeg"

    # the verifier edits the tests (adds creatinine) while confirming
    new_tests = [str(catalog[c].id) for c in ("CBC", "FBS", "CREAT")]
    r = client.post(f"{S}/orders/{order['id']}/verify", json={"test_ids": new_tests}, headers=verifier)
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "AWAITING_PAYMENT"

    seen = client.get(f"{P}/orders/{order['order_code']}", headers=patient).json()
    assert seen["status"] == "AWAITING_PAYMENT"
    assert seen["total"] == 40000 + 15000 + 30000 == seen["amount_due"]
    fbs = next(i for i in seen["items"] if i["test_code"] == "FBS")
    assert fbs["price_snapshot"] == 15000
    assert fbs["fasting_required"] is True and fbs["prep_en"] and fbs["prep_bn"]
    assert seen["needs_fasting"] is True
    assert [s["state"] for s in seen["timeline"]][:3] == ["done", "done", "current"]
    assert _sms_templates(db, order["id"]) == ["order_submitted", "order_verified"]
    verified_sms = db.scalars(select(Notification).where(Notification.template_key == "order_verified")).one()
    assert "৳৮৫০" in verified_sms.body  # Bangla numerals in the Bangla SMS


def test_clarification_round_trip_and_rejection(
    client: TestClient, db: Session, catalog: dict[str, Any], staff_headers: Any
) -> None:
    patient = patient_login(client)
    order = _submit(client, patient, catalog, "TSH")
    verifier = staff_headers(Role.VERIFIER)
    r = client.post(f"{S}/orders/{order['id']}/clarify", json={"reason": "Page 2 is unreadable"}, headers=verifier)
    assert r.json()["status"] == "NEEDS_CLARIFICATION"
    seen = client.get(f"{P}/orders/{order['id']}", headers=patient).json()
    assert seen["clarification_note"] == "Page 2 is unreadable"
    assert seen["timeline"][1]["state"] == "error"

    files = [("files", ("p2.png", PNG, "image/png"))]
    r = client.post(f"{P}/orders/{order['id']}/prescription-images", files=files, headers=patient)
    assert r.json()["prescription"]["image_count"] == 2
    r = client.post(f"{P}/orders/{order['id']}/clarification", json={"note": "Clear photo added"}, headers=patient)
    assert r.json()["status"] == "PENDING_VERIFICATION"

    r = client.post(f"{S}/orders/{order['id']}/reject", json={"reason": "Test not offered"}, headers=verifier)
    assert r.json()["status"] == "REJECTED"
    assert _sms_templates(db, order["id"]) == ["order_submitted", "order_clarification", "order_rejected"]
    # a rejected order can't be verified any more
    assert client.post(f"{S}/orders/{order['id']}/verify", json={}, headers=verifier).status_code == 409


def test_prescription_rules(client: TestClient, catalog: dict[str, Any]) -> None:
    patient = patient_login(client)
    pid = add_self(client, patient)
    # tests that require a prescription can't be ordered without one
    r = client.post(f"{P}/orders", json={"patient_id": pid, "test_ids": [str(catalog["CBC"].id)]}, headers=patient)
    assert r.json()["code"] == "PRESCRIPTION_REQUIRED"
    # blood grouping doesn't need one (placeholder catalog flag)
    r = client.post(f"{P}/orders", json={"patient_id": pid, "test_ids": [str(catalog["BG"].id)]}, headers=patient)
    assert r.status_code == 201
    # 1–3 images, real images only, ≤ 1 MB each
    four = [("files", (f"{i}.jpg", JPEG, "image/jpeg")) for i in range(4)]
    assert client.post(f"{P}/prescriptions", data={"patient_id": pid}, files=four, headers=patient).status_code == 422
    fake = [("files", ("x.jpg", b"not an image at all", "image/jpeg"))]
    r = client.post(f"{P}/prescriptions", data={"patient_id": pid}, files=fake, headers=patient)
    assert r.json()["code"] == "UNSUPPORTED_IMAGE"
    big = [("files", ("big.jpg", JPEG + b"\x00" * 1_300_000, "image/jpeg"))]
    r = client.post(f"{P}/prescriptions", data={"patient_id": pid}, files=big, headers=patient)
    assert r.json()["code"] == "IMAGE_TOO_LARGE"


def test_orders_are_isolated_between_accounts(client: TestClient, catalog: dict[str, Any]) -> None:
    alice = patient_login(client, "01711111111")
    order = _submit(client, alice, catalog, "CBC")
    bob = patient_login(client, "01722222222")
    bob_pid = add_self(client, bob, "Bob", "M")
    assert client.get(f"{P}/orders/{order['id']}", headers=bob).status_code == 404
    assert client.get(f"{P}/orders/{order['order_code']}", headers=bob).status_code == 404
    assert client.post(f"{P}/orders/{order['id']}/cancel", headers=bob).status_code == 404
    assert client.get(f"{P}/prescriptions/{order['prescription']['id']}/images/1", headers=bob).status_code == 404
    # Bob can't order for Alice's patient, nor attach Alice's prescription
    r = client.post(
        f"{P}/orders",
        json={"patient_id": order["patient"]["id"], "test_ids": [str(catalog["BG"].id)]},
        headers=bob,
    )
    assert r.status_code == 404
    r = client.post(
        f"{P}/orders",
        json={
            "patient_id": bob_pid,
            "prescription_id": order["prescription"]["id"],
            "test_ids": [str(catalog["BG"].id)],
        },
        headers=bob,
    )
    assert r.json()["code"] == "PRESCRIPTION_NOT_USABLE"
    assert client.get(f"{P}/orders", headers=bob).json() == []


def test_price_is_snapshotted(client: TestClient, db: Session, catalog: dict[str, Any], staff_headers: Any) -> None:
    patient = patient_login(client)
    order = _submit(client, patient, catalog, "CREAT")
    with clock.frozen(clock.now() + timedelta(seconds=5)):
        catalog_service.set_price(db, catalog["CREAT"], 99900, catalog["CREAT"].prices[0].fee_category, SYSTEM)
        db.flush()
        seen = client.get(f"{P}/orders/{order['id']}", headers=patient).json()
        assert seen["items"][0]["price_snapshot"] == 30000 and seen["total"] == 30000
        verifier = staff_headers(Role.VERIFIER)
        r = client.post(f"{S}/orders/{order['id']}/verify", json={}, headers=verifier)
        assert r.json()["total"] == 30000
        # a new order takes today's price
        new = _submit_helpdesk(client, staff_headers, catalog, "CREAT")
        assert new["total"] == 99900


def _submit_helpdesk(
    client: TestClient, staff_headers: Any, catalog: dict[str, Any], *tests: str, **extra: Any
) -> dict[str, Any]:
    h = staff_headers(Role.HELP_DESK)
    p = client.post(
        f"{S}/patients",
        json={"full_name": f"Walkin {tests[0]}", "sex": "M", "age_years": 61, "mobile": "01911000222", "force": True},
        headers=h,
    ).json()
    r = client.post(
        f"{S}/orders/walkin",
        json={"patient_id": p["id"], "test_ids": [str(catalog[c].id) for c in tests], **extra},
        headers=h,
    )
    assert r.status_code == 201, r.text
    body: dict[str, Any] = r.json()
    body["_headers"] = h
    return body


def test_helpdesk_walkin_goes_straight_to_awaiting_payment(
    client: TestClient, db: Session, catalog: dict[str, Any], staff_headers: Any
) -> None:
    order = _submit_helpdesk(client, staff_headers, catalog, "CBC", "CREAT", "URINE_RE")
    assert order["status"] == "AWAITING_PAYMENT"
    assert order["channel"] == "HELPDESK"
    assert order["verified_by_staff_id"] is not None
    assert codes.parse_order_code(order["order_code"]) == order["order_code"]
    assert order["total"] == 40000 + 30000 + 20000
    assert _sms_templates(db, order["id"]) == ["walkin_created"]
    sms = db.scalars(select(Notification).where(Notification.order_id == order["id"])).one()
    assert codes.format_order_code(order["order_code"]) in sms.body

    # the bank teller / any counter finds it by code in any format
    dashed = codes.format_order_code(order["order_code"])
    found = client.get(f"{S}/orders/{dashed.replace('-', ' ')}", headers=order["_headers"]).json()
    assert found["id"] == order["id"]
    # a mistyped code is caught by the check digit
    bad = order["order_code"][:-1] + str((int(order["order_code"][-1]) + 1) % 10)
    r = client.get(f"{S}/orders/{bad}", headers=order["_headers"])
    assert r.status_code == 422 and r.json()["code"] == "CODE_MISTYPED"


def test_waiver_flow(client: TestClient, db: Session, catalog: dict[str, Any], staff_headers: Any) -> None:
    order = _submit_helpdesk(
        client, staff_headers, catalog, "CBC", fee_category="POOR_FUND", waiver_reason="Poor fund card #123"
    )
    helpdesk = order["_headers"]
    assert order["waivers"][0]["status"] == "REQUESTED"
    assert order["fee_category"] == "GENERAL"  # unchanged until approved

    # the requester can't approve their own request even with the permission
    approver = staff_headers(Role.WAIVER_APPROVER)
    queue = client.get(f"{S}/waivers", headers=approver).json()
    waiver_id = queue[0]["waiver"]["id"]
    assert queue[0]["order"]["id"] == order["id"]
    r = client.post(
        f"{S}/waivers/{waiver_id}/decision",
        json={"approve": True, "discount": 40000, "reason": "Card verified"},
        headers=helpdesk,
    )
    assert r.status_code == 403

    r = client.post(
        f"{S}/waivers/{waiver_id}/decision",
        json={"approve": True, "discount": 40000, "reason": "Card verified"},
        headers=approver,
    )
    assert r.status_code == 200, r.text
    detail = client.get(f"{S}/orders/{order['id']}", headers=helpdesk).json()
    assert detail["status"] == "PAID"
    assert detail["fee_category"] == "POOR_FUND" and detail["total"] == 0 and detail["discount"] == 40000
    payment = db.scalars(select(Payment).where(Payment.order_id == order["id"])).one()
    assert (payment.method.value, payment.status.value, payment.amount) == ("WAIVER", "SUCCESS", 40000)
    actions = {a.action for a in db.scalars(select(AuditLog).where(AuditLog.entity_id == waiver_id))}
    assert {"waiver_request.REQUESTED", "waiver_request.APPROVED"} <= actions
    # decided once only
    r = client.post(f"{S}/waivers/{waiver_id}/decision", json={"approve": False, "reason": "again"}, headers=approver)
    assert r.status_code == 409


def test_partial_waiver_keeps_order_awaiting_payment(
    client: TestClient, catalog: dict[str, Any], staff_headers: Any
) -> None:
    order = _submit_helpdesk(client, staff_headers, catalog, "LIPID")
    helpdesk = order["_headers"]
    r = client.post(
        f"{S}/orders/{order['id']}/waivers",
        json={"fee_category": "CONCESSION", "reason": "Staff family"},
        headers=helpdesk,
    )
    assert r.status_code == 201
    approver = staff_headers(Role.WAIVER_APPROVER)
    too_much = client.post(
        f"{S}/waivers/{r.json()['id']}/decision",
        json={"approve": True, "discount": 100001, "reason": "x" * 3},
        headers=approver,
    )
    assert too_much.json()["code"] == "DISCOUNT_EXCEEDS_TOTAL"
    client.post(
        f"{S}/waivers/{r.json()['id']}/decision",
        json={"approve": True, "discount": 50000, "reason": "Half"},
        headers=approver,
    )
    detail = client.get(f"{S}/orders/{order['id']}", headers=helpdesk).json()
    assert detail["status"] == "AWAITING_PAYMENT" and detail["total"] == 50000 and detail["amount_due"] == 50000


def test_cancel_rules(client: TestClient, catalog: dict[str, Any], staff_headers: Any) -> None:
    patient = patient_login(client)
    order = _submit(client, patient, catalog, "CBC")
    r = client.post(f"{P}/orders/{order['id']}/cancel", headers=patient)
    assert r.json()["status"] == "CANCELLED"
    assert client.post(f"{P}/orders/{order['id']}/cancel", headers=patient).status_code == 409
    # a fully waived (PAID) order is no longer cancellable by the help desk
    paid = _submit_helpdesk(client, staff_headers, catalog, "BG", fee_category="FREE", waiver_reason="Emergency")
    approver = staff_headers(Role.WAIVER_APPROVER)
    client.post(
        f"{S}/waivers/{paid['waivers'][0]['id']}/decision",
        json={"approve": True, "discount": 15000, "reason": "Emergency approved"},
        headers=approver,
    )
    r = client.post(f"{S}/orders/{paid['id']}/cancel", json={"reason": "changed mind"}, headers=paid["_headers"])
    assert r.status_code == 409


def test_staff_permissions(client: TestClient, catalog: dict[str, Any], staff_headers: Any) -> None:
    teller = staff_headers(Role.BANK_TELLER)
    assert client.get(f"{S}/verification/queue", headers=teller).status_code == 403
    collector = staff_headers(Role.COLLECTOR)
    assert client.post(f"{S}/orders/walkin", json={}, headers=collector).status_code == 403
    verifier = staff_headers(Role.VERIFIER)
    assert client.get(f"{S}/waivers", headers=verifier).status_code == 403


def test_overdue_flag(client: TestClient, catalog: dict[str, Any], staff_headers: Any) -> None:
    patient = patient_login(client)
    order = _submit(client, patient, catalog, "CBC")
    with clock.frozen(clock.now() + timedelta(hours=5)):
        verifier = staff_headers(Role.VERIFIER)
        rows = client.get(f"{S}/verification/queue", headers=verifier).json()
        assert next(r for r in rows if r["id"] == order["id"])["overdue"] is True
        stats = client.get(f"{S}/orders/stats", headers=verifier).json()
        assert stats["OVERDUE_VERIFICATION"] >= 1
