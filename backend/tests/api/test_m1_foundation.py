"""M1 acceptance: staff login with TOTP, lockout, idle lock, permissions, append-only audit log."""

from __future__ import annotations

from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from app.core import audit, clock
from app.core.actor import SYSTEM
from app.core.security import new_totp_secret, totp_now
from app.modules.identity.permissions import Role
from tests.conftest import PASSWORD, login, make_staff


def test_health(client: TestClient) -> None:
    r = client.get("/api/v1/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_plain_role_logs_in_without_totp(client: TestClient, db: Session) -> None:
    staff = make_staff(db, Role.HELP_DESK)
    headers = login(client, staff, station="Counter 3")
    me = client.get("/api/v1/staff/auth/me", headers=headers).json()
    assert me["username"] == staff.username
    assert me["station"] == "Counter 3"
    assert "order.create_walkin" in me["permissions"]


def test_pathologist_must_enrol_totp_then_login_with_totp(client: TestClient, db: Session) -> None:
    staff = make_staff(db, Role.PATHOLOGIST)
    r = client.post("/api/v1/staff/auth/login", json={"username": staff.username, "password": PASSWORD})
    body = r.json()
    assert body["status"] == "TOTP_ENROLL"
    assert body["otpauth_uri"].startswith("otpauth://totp/")
    bad = client.post("/api/v1/staff/auth/totp", json={"challenge": body["challenge"], "code": "000000"})
    assert bad.status_code == 401
    ok = client.post(
        "/api/v1/staff/auth/totp", json={"challenge": body["challenge"], "code": totp_now(body["totp_secret"])}
    )
    assert ok.status_code == 200 and ok.json()["status"] == "OK"
    db.refresh(staff)
    assert staff.totp_enabled
    # second login now requires (not enrols) TOTP
    r2 = client.post("/api/v1/staff/auth/login", json={"username": staff.username, "password": PASSWORD})
    assert r2.json()["status"] == "TOTP_REQUIRED"
    r3 = client.post(
        "/api/v1/staff/auth/totp", json={"challenge": r2.json()["challenge"], "code": totp_now(staff.totp_secret or "")}
    )
    assert r3.json()["status"] == "OK"
    me = client.get("/api/v1/staff/auth/me", headers={"Authorization": f"Bearer {r3.json()['access_token']}"})
    assert me.json()["totp_enabled"] is True


def test_totp_secret_is_encrypted_at_rest(db: Session) -> None:
    secret = new_totp_secret()
    staff = make_staff(db, Role.LAB_ADMIN, totp_secret=secret)
    raw = db.execute(text("SELECT totp_secret FROM staff WHERE id = :id"), {"id": staff.id}).scalar_one()
    assert raw != secret and secret not in raw


def test_lockout_after_five_failures(client: TestClient, db: Session) -> None:
    staff = make_staff(db, Role.HELP_DESK)
    for _ in range(5):
        r = client.post("/api/v1/staff/auth/login", json={"username": staff.username, "password": "wrong"})
        assert r.status_code == 401
    r = client.post("/api/v1/staff/auth/login", json={"username": staff.username, "password": PASSWORD})
    assert r.status_code == 423
    assert r.json()["code"] == "ACCOUNT_LOCKED"


def test_idle_lock_and_unlock(client: TestClient, db: Session) -> None:
    staff = make_staff(db, Role.COLLECTOR)
    headers = login(client, staff)
    with clock.frozen(clock.now() + timedelta(minutes=31)):
        r = client.get("/api/v1/staff/auth/me", headers=headers)
        assert r.status_code == 423
        assert r.json()["code"] == "SESSION_LOCKED"
        assert client.post("/api/v1/staff/auth/unlock", json={"secret": "nope"}, headers=headers).status_code == 401
        assert client.post("/api/v1/staff/auth/unlock", json={"secret": PASSWORD}, headers=headers).status_code == 200
        assert client.get("/api/v1/staff/auth/me", headers=headers).status_code == 200


def test_session_expires_after_12_hours(client: TestClient, db: Session) -> None:
    staff = make_staff(db, Role.COLLECTOR)
    headers = login(client, staff)
    with clock.frozen(clock.now() + timedelta(hours=12, minutes=1)):
        assert client.get("/api/v1/staff/auth/me", headers=headers).status_code == 401


def test_permission_required(client: TestClient, db: Session) -> None:
    headers = login(client, make_staff(db, Role.BANK_TELLER))
    r = client.get("/api/v1/staff/admin/staff", headers=headers)
    assert r.status_code == 403
    assert r.json()["code"] == "MISSING_PERMISSION"


def test_only_super_admin_grants_admin_roles(client: TestClient, db: Session) -> None:
    lab_admin = login(client, make_staff(db, Role.LAB_ADMIN, totp_secret=new_totp_secret()))
    payload = {
        "username": "newadmin",
        "full_name": "New Admin",
        "password": "long-enough-pass",
        "roles": [{"role": "SUPER_ADMIN"}],
    }
    assert client.post("/api/v1/staff/admin/staff", json=payload, headers=lab_admin).status_code == 403
    payload["roles"] = [{"role": "HELP_DESK"}]
    assert client.post("/api/v1/staff/admin/staff", json=payload, headers=lab_admin).status_code == 201


def test_audit_log_update_and_delete_fail_at_db_level(db: Session) -> None:
    row = audit.record(db, SYSTEM, "test.event")
    db.flush()
    with pytest.raises(DBAPIError), db.begin_nested():
        db.execute(text("UPDATE audit_log SET action = 'tampered' WHERE id = :id"), {"id": row.id})
    with pytest.raises(DBAPIError), db.begin_nested():
        db.execute(text("DELETE FROM audit_log WHERE id = :id"), {"id": row.id})


def test_error_shape(client: TestClient) -> None:
    r = client.get("/api/v1/staff/auth/me")
    assert r.status_code == 401
    assert set(r.json()) == {"code", "message_key", "params"}


def test_new_staff_must_change_password_before_working(client: TestClient, db: Session) -> None:
    admin = login(client, make_staff(db, Role.LAB_ADMIN, totp_secret=new_totp_secret()))
    payload = {
        "username": "newclerk",
        "full_name": "New Clerk",
        "password": "temporary-pass-1",
        "roles": [{"role": "HELP_DESK"}],
    }
    assert client.post("/api/v1/staff/admin/staff", json=payload, headers=admin).status_code == 201
    r = client.post("/api/v1/staff/auth/login", json={"username": "newclerk", "password": "temporary-pass-1"})
    headers = {"Authorization": f"Bearer {r.json()['access_token']}"}
    assert client.get("/api/v1/staff/auth/me", headers=headers).json()["must_change_password"] is True
    r = client.get("/api/v1/staff/patients", params={"q": "abc"}, headers=headers)
    assert r.status_code == 403 and r.json()["code"] == "PASSWORD_CHANGE_REQUIRED"
    r = client.post(
        "/api/v1/staff/auth/me/password",
        json={"current_password": "temporary-pass-1", "new_password": "my-own-secret-99"},
        headers=headers,
    )
    assert r.status_code == 204
    assert client.get("/api/v1/staff/patients", params={"q": "abc"}, headers=headers).status_code == 200


def test_pin_unlocks_an_idle_session(client: TestClient, db: Session) -> None:
    staff = make_staff(db, Role.COLLECTOR)
    headers = login(client, staff)
    r = client.post("/api/v1/staff/auth/me/pin", json={"password": PASSWORD, "pin": "4821"}, headers=headers)
    assert r.status_code == 204
    assert client.get("/api/v1/staff/auth/me", headers=headers).json()["has_pin"] is True
    with clock.frozen(clock.now() + timedelta(minutes=31)):
        assert client.get("/api/v1/staff/auth/me", headers=headers).status_code == 423
        assert client.post("/api/v1/staff/auth/unlock", json={"secret": "4821"}, headers=headers).status_code == 200
