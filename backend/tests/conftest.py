"""Test harness: real PostgreSQL (docker). A fresh `bmu_test` database is migrated with Alembic once
per run (so migrations are tested too); each test runs inside a transaction that is rolled back.
Concurrency tests use real committed sessions and truncate afterwards."""

from __future__ import annotations

import os
import tempfile
import uuid
from collections.abc import Iterator
from pathlib import Path
from typing import Any

# --- environment must be set before the app reads settings -------------------------------------
_TEST_DB = os.environ.get("TEST_DATABASE_URL", "postgresql+psycopg://bmu:bmu@localhost:55432/bmu_test")
os.environ["DATABASE_URL"] = _TEST_DB
os.environ["ENV"] = "test"
os.environ["STORAGE_BACKEND"] = "local"
os.environ["STORAGE_LOCAL_DIR"] = tempfile.mkdtemp(prefix="bmu-storage-")
os.environ["SMS_PROVIDER"] = "mock"
os.environ["PAYMENT_PROVIDER"] = "mock"
os.environ["CELERY_ENABLED"] = "false"
os.environ["WEB_PUSH_ENABLED"] = "false"
os.environ["PADES_ENABLED"] = "false"
os.environ["OCR_PROVIDER"] = "mock"
os.environ["ANALYZER_TOKEN"] = "test-analyzer-token"

import pytest  # noqa: E402
from alembic.config import Config  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine, text  # noqa: E402
from sqlalchemy.engine import make_url  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from alembic import command  # noqa: E402
from app.core import clock  # noqa: E402
from app.core.security import hash_password, totp_now  # noqa: E402
from app.db import get_db, get_engine  # noqa: E402
from app.main import app  # noqa: E402
from app.modules.identity.models import Staff, StaffRole  # noqa: E402
from app.modules.identity.permissions import Role  # noqa: E402

BACKEND = Path(__file__).resolve().parent.parent
PASSWORD = "correct-horse-battery"


def _recreate_database() -> None:
    url = make_url(_TEST_DB)
    admin = create_engine(url.set(database="postgres"), isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        conn.execute(
            text(
                "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = :d AND pid <> pg_backend_pid()"
            ),
            {"d": url.database},
        )
        conn.execute(text(f'DROP DATABASE IF EXISTS "{url.database}"'))
        conn.execute(text(f'CREATE DATABASE "{url.database}"'))
    admin.dispose()


@pytest.fixture(scope="session", autouse=True)
def _database() -> Iterator[None]:
    _recreate_database()
    cfg = Config(str(BACKEND / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND / "alembic"))
    os.environ["ALEMBIC_DATABASE_URL"] = _TEST_DB
    command.upgrade(cfg, "head")
    yield
    get_engine().dispose()


@pytest.fixture(autouse=True)
def _reset_clock() -> Iterator[None]:
    yield
    clock.reset()


@pytest.fixture
def db() -> Iterator[Session]:
    connection = get_engine().connect()
    trans = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint", expire_on_commit=False)
    try:
        yield session
    finally:
        session.close()
        if trans.is_active:
            trans.rollback()
        connection.close()


@pytest.fixture
def client(db: Session) -> Iterator[TestClient]:
    app.dependency_overrides[get_db] = lambda: db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def committed() -> Iterator[None]:
    """For concurrency tests that need real commits: truncate every table afterwards."""
    yield
    engine = get_engine()
    with engine.begin() as conn:
        tables = (
            conn.execute(
                text("SELECT tablename FROM pg_tables WHERE schemaname='public' AND tablename <> 'alembic_version'")
            )
            .scalars()
            .all()
        )
        if tables:
            conn.execute(text("TRUNCATE " + ", ".join(f'"{t}"' for t in tables) + " CASCADE"))


# ---- staff helpers ------------------------------------------------------------------------------


def make_staff(
    db: Session,
    *roles: Role | tuple[Role, uuid.UUID | None],
    username: str | None = None,
    totp_secret: str | None = None,
) -> Staff:
    role_rows = []
    for r in roles:
        role, dept = (r, None) if isinstance(r, Role) else r
        role_rows.append(StaffRole(id=uuid.uuid4(), role=role, department_id=dept))
    staff = Staff(
        id=uuid.uuid4(),
        username=username or f"user{uuid.uuid4().hex[:8]}",
        full_name="Test Staff",
        password_hash=hash_password(PASSWORD),
        roles=role_rows,
        totp_secret=totp_secret,
        totp_enabled=totp_secret is not None,
    )
    db.add(staff)
    db.flush()
    return staff


def login(client: TestClient, staff: Staff, station: str | None = "S1") -> dict[str, str]:
    r = client.post(
        "/api/v1/staff/auth/login", json={"username": staff.username, "password": PASSWORD, "station": station}
    )
    assert r.status_code == 200, r.text
    body: dict[str, Any] = r.json()
    if body["status"] != "OK":
        secret = body.get("totp_secret") or staff.totp_secret
        assert secret
        r = client.post("/api/v1/staff/auth/totp", json={"challenge": body["challenge"], "code": totp_now(secret)})
        assert r.status_code == 200, r.text
        body = r.json()
    return {"Authorization": f"Bearer {body['access_token']}"}


@pytest.fixture
def staff_headers(client: TestClient, db: Session):  # type: ignore[no-untyped-def]
    """`staff_headers(Role.HELP_DESK)` -> auth headers for a fresh staff user with those roles."""

    def make(*roles: Role | tuple[Role, uuid.UUID | None]) -> dict[str, str]:
        return login(client, make_staff(db, *roles))

    return make


# ---- M2/M3 helpers ------------------------------------------------------------------------------

try:  # WeasyPrint needs Pango; it is present in the Docker image (and CI), not on a bare Windows host.
    import weasyprint  # noqa: F401

    HAS_WEASYPRINT = True
except (OSError, ImportError):
    HAS_WEASYPRINT = False


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    if HAS_WEASYPRINT:
        return
    skip = pytest.mark.skip(reason="WeasyPrint/Pango not installed here; runs in the Docker image and CI")
    for item in items:
        if "pdf" in item.keywords:
            item.add_marker(skip)


@pytest.fixture(autouse=True)
def _clear_mock_sms() -> Iterator[None]:
    from app.modules.notifications.providers import MockSms

    MockSms.clear()
    yield


@pytest.fixture
def catalog(db: Session) -> dict[str, Any]:
    """The PLACEHOLDER seed catalog, imported inside the test transaction. Returns {code: LabTest}."""
    from sqlalchemy import select

    from app.modules.catalog.models import LabTest
    from app.modules.catalog.seed import seed_catalog

    seed_catalog(db, False)
    db.flush()
    return {t.code: t for t in db.scalars(select(LabTest))}


def patient_login(client: TestClient, mobile: str = "01712345678") -> dict[str, str]:
    r = client.post("/api/v1/patient/auth/otp/request", json={"mobile": mobile})
    assert r.status_code == 200, r.text
    code = r.json()["debug_code"]
    r = client.post("/api/v1/patient/auth/otp/verify", json={"mobile": mobile, "code": code})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def add_self(client: TestClient, headers: dict[str, str], name: str = "Rahima Begum", sex: str = "F") -> str:
    r = client.post(
        "/api/v1/patient/patients",
        json={"full_name": name, "sex": sex, "age_years": 34, "relation_to_account": "SELF"},
        headers=headers,
    )
    assert r.status_code == 201, r.text
    return str(r.json()["id"])


# Smallest byte strings that pass the server's image sniffing (JPEG / PNG magic numbers).
JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 2048
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 2048
