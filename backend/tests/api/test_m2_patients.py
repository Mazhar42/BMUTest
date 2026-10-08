"""M2 acceptance: patient OTP login (rate limits, attempts, refresh rotation), family profiles, account
isolation, staff patient search with duplicate warning."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core import clock
from app.core.errors import Invalid
from app.modules.identity.permissions import Role
from app.modules.notifications.providers import MockSms
from app.modules.patients.service import normalize_mobile
from tests.conftest import add_self, patient_login

OTP = "/api/v1/patient/auth/otp"


@pytest.mark.parametrize(
    "raw",
    ["01712345678", "+8801712345678", "8801712345678", "01712-345678", "০১৭১২৩৪৫৬৭৮", " 0171 234 5678 "],
)
def test_mobile_normalisation(raw: str) -> None:
    assert normalize_mobile(raw) == "+8801712345678"


@pytest.mark.parametrize("raw", ["0171234567", "01212345678", "abc", "+15551234567", ""])
def test_mobile_rejects_invalid(raw: str) -> None:
    with pytest.raises(Invalid):
        normalize_mobile(raw)


def test_otp_login_sends_sms_and_stores_no_plain_code(client: TestClient, db: Session) -> None:
    from sqlalchemy import select

    from app.modules.notifications.models import Notification
    from app.modules.patients.models import OtpChallenge

    r = client.post(f"{OTP}/request", json={"mobile": "01712345678", "lang": "en"})
    assert r.status_code == 200
    code = r.json()["debug_code"]
    sms = MockSms.last_to("+8801712345678")
    assert sms is not None and code in sms.body
    stored = db.scalars(select(Notification).where(Notification.to == "+8801712345678")).one()
    assert code not in stored.body and stored.params["otp"] == "***"
    challenge = db.scalars(select(OtpChallenge)).one()
    assert code not in challenge.code_hash

    r = client.post(f"{OTP}/verify", json={"mobile": "+8801712345678", "code": code})
    assert r.status_code == 200
    headers = {"Authorization": f"Bearer {r.json()['access_token']}"}
    me = client.get("/api/v1/patient/me", headers=headers).json()
    assert me["mobile"] == "+8801712345678" and me["patients"] == []
    # a code works only once
    assert client.post(f"{OTP}/verify", json={"mobile": "01712345678", "code": code}).status_code == 401


def test_otp_rate_limit_per_mobile(client: TestClient) -> None:
    for _ in range(3):
        assert client.post(f"{OTP}/request", json={"mobile": "01812345678"}).status_code == 200
    r = client.post(f"{OTP}/request", json={"mobile": "01812345678"})
    assert r.status_code == 429
    assert r.json()["code"] == "OTP_RATE_LIMITED"
    assert r.json()["params"]["minutes"] >= 1
    # another number is not affected
    assert client.post(f"{OTP}/request", json={"mobile": "01912345678"}).status_code == 200
    # the window slides: after 15 minutes the number can request again
    with clock.frozen(clock.now() + timedelta(minutes=16)):
        assert client.post(f"{OTP}/request", json={"mobile": "01812345678"}).status_code == 200


def test_otp_rate_limit_per_ip(client: TestClient) -> None:
    from app.config import get_settings

    limit = get_settings().otp_send_limit_per_ip
    for i in range(limit):
        assert client.post(f"{OTP}/request", json={"mobile": f"0171{i:07d}"}).status_code == 200
    r = client.post(f"{OTP}/request", json={"mobile": "01799999999"})
    assert r.status_code == 429


def test_otp_max_attempts_and_expiry(client: TestClient) -> None:
    code = client.post(f"{OTP}/request", json={"mobile": "01612345678"}).json()["debug_code"]
    wrong = "000000" if code != "000000" else "111111"
    for _ in range(4):
        r = client.post(f"{OTP}/verify", json={"mobile": "01612345678", "code": wrong})
        assert r.json()["code"] == "OTP_INVALID"
    r = client.post(f"{OTP}/verify", json={"mobile": "01612345678", "code": wrong})
    assert r.json()["code"] == "OTP_TOO_MANY_ATTEMPTS"
    # even the right code no longer works
    assert client.post(f"{OTP}/verify", json={"mobile": "01612345678", "code": code}).status_code == 401

    code = client.post(f"{OTP}/request", json={"mobile": "01612345678"}).json()["debug_code"]
    with clock.frozen(clock.now() + timedelta(minutes=6)):
        r = client.post(f"{OTP}/verify", json={"mobile": "01612345678", "code": code})
        assert r.json()["code"] == "OTP_EXPIRED"


def test_refresh_rotation_and_reuse_detection(client: TestClient) -> None:
    patient_login(client, "01512345678")
    old_cookie = client.cookies.get("bmu_refresh")
    assert old_cookie
    # CSRF: the custom header is required
    assert client.post("/api/v1/patient/auth/refresh").status_code == 403
    r = client.post("/api/v1/patient/auth/refresh", headers={"X-Requested-With": "bmu"})
    assert r.status_code == 200
    new_cookie = client.cookies.get("bmu_refresh")
    assert new_cookie and new_cookie != old_cookie
    # replaying the rotated token revokes the whole family
    client.cookies.set("bmu_refresh", old_cookie, path="/api/v1/patient/auth")
    r = client.post("/api/v1/patient/auth/refresh", headers={"X-Requested-With": "bmu"})
    assert r.json()["code"] == "REFRESH_REUSED"
    client.cookies.set("bmu_refresh", new_cookie, path="/api/v1/patient/auth")
    r = client.post("/api/v1/patient/auth/refresh", headers={"X-Requested-With": "bmu"})
    assert r.status_code == 401


def test_access_token_expires(client: TestClient) -> None:
    headers = patient_login(client)
    with clock.frozen(clock.now() + timedelta(minutes=16)):
        assert client.get("/api/v1/patient/me", headers=headers).status_code == 401


def test_family_profiles(client: TestClient) -> None:
    headers = patient_login(client)
    add_self(client, headers)
    r = client.post(
        "/api/v1/patient/patients",
        json={"full_name": "Karim", "sex": "M", "date_of_birth": "2015-03-01", "relation_to_account": "CHILD"},
        headers=headers,
    )
    assert r.status_code == 201
    assert r.json()["mobile"] == "+8801712345678"  # inherits the account mobile
    # only one SELF profile
    dup = client.post(
        "/api/v1/patient/patients",
        json={"full_name": "Another Me", "sex": "F", "age_years": 30, "relation_to_account": "SELF"},
        headers=headers,
    )
    assert dup.json()["code"] == "SELF_PROFILE_EXISTS"
    # date of birth XOR age
    bad = client.post(
        "/api/v1/patient/patients",
        json={"full_name": "No Age", "sex": "F", "relation_to_account": "SPOUSE"},
        headers=headers,
    )
    assert bad.status_code == 422
    assert len(client.get("/api/v1/patient/patients", headers=headers).json()) == 2


def test_patient_cannot_access_another_accounts_patients(client: TestClient) -> None:
    alice = patient_login(client, "01711111111")
    alice_pid = add_self(client, alice, "Alice")
    bob = patient_login(client, "01722222222")
    add_self(client, bob, "Bob", "M")

    assert client.get(f"/api/v1/patient/patients/{alice_pid}", headers=bob).status_code == 404
    r = client.patch(f"/api/v1/patient/patients/{alice_pid}", json={"full_name": "Hacked"}, headers=bob)
    assert r.status_code == 404
    names = [p["full_name"] for p in client.get("/api/v1/patient/patients", headers=bob).json()]
    assert names == ["Bob"]
    # the patient zone rejects staff tokens and vice versa
    assert client.get("/api/v1/staff/auth/me", headers=bob).status_code == 401


def test_staff_search_and_duplicate_warning(client: TestClient, staff_headers: Any) -> None:
    h = staff_headers(Role.HELP_DESK)
    body = {"full_name": "Abdul Karim", "sex": "M", "age_years": 52, "mobile": "01711000111"}
    r = client.post("/api/v1/staff/patients", json=body, headers=h)
    assert r.status_code == 201, r.text
    pid = r.json()["id"]
    # same mobile → duplicate warning with the candidate
    r = client.post("/api/v1/staff/patients", json={**body, "full_name": "Abdul Karim Mia"}, headers=h)
    assert r.status_code == 409 and r.json()["code"] == "POSSIBLE_DUPLICATE"
    assert r.json()["params"]["candidates"][0]["id"] == pid
    # similar name, same sex and age, different mobile → still warned
    r = client.post("/api/v1/staff/patients", json={**body, "mobile": "01811000111"}, headers=h)
    assert r.status_code == 409 and r.json()["params"]["candidates"][0]["reason"] == "NAME"
    # staff can override after checking
    r = client.post("/api/v1/staff/patients", json={**body, "mobile": "01811000111", "force": True}, headers=h)
    assert r.status_code == 201

    by_mobile = client.get("/api/v1/staff/patients", params={"q": "01711-000111"}, headers=h).json()
    assert [p["id"] for p in by_mobile] == [pid]
    by_name = client.get("/api/v1/staff/patients", params={"q": "karim"}, headers=h).json()
    assert pid in [p["id"] for p in by_name]
