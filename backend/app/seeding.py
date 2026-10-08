"""`make seed`: placeholder catalog + (with --demo) staff for every role, display device, capacity.

Each milestone extends `run_seed`. Medical/financial values come only from `backend/seed/*`
(headed PLACEHOLDER — must be confirmed by BMU laboratory)."""

from __future__ import annotations

import importlib
import uuid
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.modules.identity.models import Staff, StaffRole
from app.modules.identity.permissions import Role

SEED_DIR = Path(__file__).resolve().parent.parent / "seed"

DEMO_PASSWORD = "bmu-demo-2026"

# username, full name, roles (role, department code | None)
DEMO_STAFF: list[tuple[str, str, list[tuple[Role, str | None]]]] = [
    ("admin", "Super Admin", [(Role.SUPER_ADMIN, None)]),
    ("labadmin", "Farhana Lab Admin", [(Role.LAB_ADMIN, None)]),
    ("helpdesk", "Rafiq Help Desk", [(Role.HELP_DESK, None)]),
    ("verifier", "Nusrat Verifier", [(Role.VERIFIER, None)]),
    ("teller", "Kamal Bank Teller", [(Role.BANK_TELLER, None)]),
    ("cashier", "Shirin Cashier", [(Role.CASHIER, None)]),
    ("collector", "Jamal Collector", [(Role.COLLECTOR, None)]),
    ("reception", "Mitu Lab Reception", [(Role.LAB_RECEPTION, None)]),
    ("tech.haem", "Sohel Technician (Haematology)", [(Role.TECHNICIAN, "HAEM")]),
    ("tech.bio", "Ruma Technician (Biochemistry)", [(Role.TECHNICIAN, "BIOCHEM")]),
    ("tech.micro", "Arif Technician (Microbiology)", [(Role.TECHNICIAN, "MICRO")]),
    ("patho", "Dr. Selina Pathologist", [(Role.PATHOLOGIST, None)]),
    ("reportdesk", "Babul Report Desk", [(Role.REPORT_DESK, None)]),
    ("waiver", "Dr. Hasan Waiver Approver", [(Role.WAIVER_APPROVER, None)]),
    ("auditor", "Tania Auditor", [(Role.AUDITOR, None)]),
    ("homecollector", "Liton Home Collector", [(Role.HOME_COLLECTOR, None)]),
]


def _department_ids(db: Session) -> dict[str, uuid.UUID]:
    try:
        from app.modules.catalog.models import Department
    except ImportError:  # before M2
        return {}
    return {d.code: d.id for d in db.scalars(select(Department))}


def seed_staff(db: Session) -> list[dict[str, Any]]:
    depts = _department_ids(db)
    created: list[dict[str, Any]] = []
    for username, name, roles in DEMO_STAFF:
        if db.scalar(select(Staff).where(Staff.username == username)):
            continue
        staff = Staff(
            id=uuid.uuid4(),
            username=username,
            full_name=name,
            password_hash=hash_password(DEMO_PASSWORD),
            roles=[StaffRole(id=uuid.uuid4(), role=r, department_id=depts.get(d) if d else None) for r, d in roles],
        )
        db.add(staff)
        created.append({"username": username, "password": DEMO_PASSWORD, "roles": [r.value for r, _ in roles]})
    return created


def run_seed(db: Session, demo: bool = False) -> dict[str, Any]:
    summary: dict[str, Any] = {}
    for step in _steps():
        summary.update(step(db, demo))
    if demo:
        db.flush()
        summary["demo_staff"] = seed_staff(db)
        summary["demo_password"] = DEMO_PASSWORD
        summary["note"] = (
            "Staff with TOTP-required roles (admin, labadmin, patho, waiver) enrol an authenticator app at first login."
        )
    return summary


def _steps() -> list[Any]:
    """Seed steps contributed by milestone modules (catalog, capacity, devices...), when present."""
    steps: list[Any] = []
    for module, fn in (
        ("app.modules.catalog.seed", "seed_catalog"),
        ("app.modules.scheduling.seed", "seed_capacity"),
    ):
        try:
            steps.append(getattr(importlib.import_module(module), fn))
        except ModuleNotFoundError:  # milestone not built yet
            continue
    return steps
