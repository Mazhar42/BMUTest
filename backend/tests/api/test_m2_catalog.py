"""M2 acceptance: idempotent CSV import, alias search in Bangla and English, price history, admin CRUD."""

from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.actor import SYSTEM
from app.modules.catalog import service
from app.modules.catalog.models import Department, LabTest, LabTestPrice
from app.modules.catalog.seed import SEED_DIR
from app.modules.identity.permissions import Role


def _counts(db: Session) -> tuple[int, int, int]:
    return (
        db.scalar(select(func.count()).select_from(Department)) or 0,
        db.scalar(select(func.count()).select_from(LabTest)) or 0,
        db.scalar(select(func.count()).select_from(LabTestPrice)) or 0,
    )


def test_seed_files_are_marked_placeholder() -> None:
    for name in ("departments.csv", "tests.csv", "parameters.csv"):
        first = (SEED_DIR / name).read_text(encoding="utf-8").splitlines()[0]
        assert "PLACEHOLDER — must be confirmed by BMU laboratory" in first


def test_import_twice_is_idempotent(db: Session) -> None:
    depts = (SEED_DIR / "departments.csv").read_text(encoding="utf-8")
    tests = (SEED_DIR / "tests.csv").read_text(encoding="utf-8")
    r1 = service.import_departments(db, depts, SYSTEM)
    t1 = service.import_tests(db, tests, SYSTEM)
    assert r1.errors == [] and t1.errors == []
    assert t1.created == 20 and t1.price_changes == 20
    after_first = _counts(db)

    r2 = service.import_departments(db, depts, SYSTEM)
    t2 = service.import_tests(db, tests, SYSTEM)
    assert (r2.created, r2.updated) == (0, 0)
    assert (t2.created, t2.updated, t2.price_changes) == (0, 0, 0)
    assert t2.unchanged == 20
    assert _counts(db) == after_first


def test_import_records_price_history(db: Session, catalog: dict[str, Any]) -> None:
    tests = (SEED_DIR / "tests.csv").read_text(encoding="utf-8")
    changed = tests.replace("CBC,Complete Blood Count", "CBC,Complete Blood Count", 1).replace(
        ",true,400,true", ",true,450,true", 1
    )
    res = service.import_tests(db, changed, SYSTEM)
    assert res.price_changes == 1
    cbc = catalog["CBC"]
    db.refresh(cbc)
    prices = sorted(cbc.prices, key=lambda p: p.effective_from)
    assert [p.amount for p in prices] == [40000, 45000]
    assert prices[0].effective_to is not None and prices[1].effective_to is None
    assert service.current_price(cbc) == 45000


def _codes(rows: list[LabTest]) -> list[str]:
    return [t.code for t in rows]


def test_search_matches_aliases_in_english(db: Session, catalog: dict[str, Any]) -> None:
    assert _codes(service.search_tests(db, "s creat"))[0] == "CREAT"
    assert _codes(service.search_tests(db, "S. Creat"))[0] == "CREAT"
    assert "LIPID" in _codes(service.search_tests(db, "cholesterol"))
    assert "ALT" in _codes(service.search_tests(db, "sgpt"))
    assert "CBC" in _codes(service.search_tests(db, "complete blood"))


def test_search_matches_aliases_in_bangla(db: Session, catalog: dict[str, Any]) -> None:
    assert _codes(service.search_tests(db, "ক্রিয়েটিনিন"))[0] == "CREAT"
    assert {"FBS", "RBS"} <= set(_codes(service.search_tests(db, "সুগার")))
    assert "NS1" in _codes(service.search_tests(db, "ডেঙ্গু"))


def test_search_tolerates_a_typo(db: Session, catalog: dict[str, Any]) -> None:
    assert "CREAT" in _codes(service.search_tests(db, "creatinin"))


def test_staff_search_api_and_permissions(client: TestClient, catalog: dict[str, Any], staff_headers: Any) -> None:
    helpdesk = staff_headers(Role.HELP_DESK)
    r = client.get("/api/v1/staff/catalog/tests", params={"q": "s creat"}, headers=helpdesk)
    assert r.status_code == 200
    assert r.json()[0]["code"] == "CREAT"
    assert r.json()[0]["price"] == 30000
    # help desk can read but not change the catalog
    r = client.post(f"/api/v1/staff/catalog/tests/{catalog['CREAT'].id}/prices", json={"amount": 1}, headers=helpdesk)
    assert r.status_code == 403
    teller = staff_headers(Role.BANK_TELLER)
    assert client.get("/api/v1/staff/catalog/tests", headers=teller).status_code == 403


def test_admin_crud_and_csv_upload(client: TestClient, db: Session, staff_headers: Any) -> None:
    admin = staff_headers((Role.SUPER_ADMIN, None))
    r = client.post(
        "/api/v1/staff/catalog/departments",
        json={"code": "TESTD", "name_en": "Test Dept", "name_bn": "পরীক্ষা বিভাগ"},
        headers=admin,
    )
    assert r.status_code == 201, r.text
    dept_id = r.json()["id"]
    r = client.post(
        "/api/v1/staff/catalog/tests",
        json={
            "code": "XTEST",
            "name_en": "X Test",
            "name_bn": "এক্স টেস্ট",
            "abbreviation": "XT",
            "aliases": ["ex test"],
            "department_id": dept_id,
            "specimen_type": "BLOOD",
            "container_type": "EDTA",
            "collection_resource": "BLOOD_COLLECTION",
            "price": 12300,
        },
        headers=admin,
    )
    assert r.status_code == 201, r.text
    test_id = r.json()["id"]
    assert r.json()["price"] == 12300
    r = client.post(f"/api/v1/staff/catalog/tests/{test_id}/prices", json={"amount": 15000}, headers=admin)
    assert [p["amount"] for p in r.json()["prices"]] == [15000, 12300]
    r = client.patch(f"/api/v1/staff/catalog/tests/{test_id}", json={"active": False}, headers=admin)
    assert r.json()["active"] is False
    assert client.get("/api/v1/staff/catalog/tests", params={"q": "ex test"}, headers=admin).json() == []

    csv_bytes = (SEED_DIR / "departments.csv").read_bytes()
    for _ in range(2):
        r = client.post(
            "/api/v1/staff/catalog/import/departments",
            files={"file": ("departments.csv", csv_bytes, "text/csv")},
            headers=admin,
        )
        assert r.status_code == 200, r.text
    assert r.json()["created"] == 0 and r.json()["unchanged"] == 5
