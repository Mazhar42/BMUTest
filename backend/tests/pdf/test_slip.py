"""M3 acceptance: the walk-in slip PDF has three parts, each with the same code, and the printed barcodes
decode back to it (pyzbar). Reprints are watermarked and audited. Needs WeasyPrint → Docker image / CI."""

from __future__ import annotations

import io
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core import codes
from app.core.models import AuditLog
from app.modules.identity.permissions import Role

pytestmark = pytest.mark.pdf

S = "/api/v1/staff"


def _walkin(client: TestClient, staff_headers: Any, catalog: dict[str, Any]) -> tuple[dict[str, Any], dict[str, str]]:
    h = staff_headers(Role.HELP_DESK)
    p = client.post(
        f"{S}/patients",
        json={
            "full_name": "Rahima Khatun",
            "full_name_bn": "রহিমা খাতুন",
            "sex": "F",
            "age_years": 45,
            "mobile": "01711223344",
            "force": True,
        },
        headers=h,
    ).json()
    r = client.post(
        f"{S}/orders/walkin",
        json={"patient_id": p["id"], "test_ids": [str(catalog[c].id) for c in ("CBC", "FBS", "CREAT", "URINE_RE")]},
        headers=h,
    )
    assert r.status_code == 201, r.text
    return r.json(), h


def _text(pdf: bytes) -> str:
    from pypdf import PdfReader

    return "\n".join(page.extract_text() or "" for page in PdfReader(io.BytesIO(pdf)).pages)


def _decode_parts(pdf: bytes) -> list[list[tuple[str, str]]]:
    """Render at 300 dpi, cut the page into its three copies and decode each one separately."""
    import pypdfium2 as pdfium
    from pyzbar import pyzbar

    image = pdfium.PdfDocument(pdf)[0].render(scale=300 / 72).to_pil().convert("L")
    w, h = image.size
    parts = [image.crop((0, h * i // 3, w, h * (i + 1) // 3)) for i in range(3)]
    return [sorted((d.type, d.data.decode()) for d in pyzbar.decode(part)) for part in parts]


def test_slip_has_three_parts_with_the_same_decodable_code(
    client: TestClient, db: Session, catalog: dict[str, Any], staff_headers: Any
) -> None:
    order, h = _walkin(client, staff_headers, catalog)
    code = order["order_code"]
    r = client.post(f"{S}/orders/{order['id']}/slip", headers=h)
    assert r.status_code == 200, r.text
    assert r.headers["content-type"] == "application/pdf"
    pdf = r.content

    from pypdf import PdfReader

    assert len(PdfReader(io.BytesIO(pdf)).pages) == 1  # one A4 page, cut in three
    text = _text(pdf)
    for part in ("PATIENT COPY", "BANK COPY", "HOSPITAL COPY"):
        assert part in text
    assert text.count(codes.format_order_code(code)) >= 3
    assert "REPRINT" not in text

    patient_copy, bank_copy, hospital_copy = _decode_parts(pdf)
    assert patient_copy == [("QRCODE", code)]  # the QR carries the code only, no personal data
    assert bank_copy == [("CODE128", code)]
    assert hospital_copy == [("CODE128", code)]


def test_reprint_is_watermarked_and_audited(
    client: TestClient, db: Session, catalog: dict[str, Any], staff_headers: Any
) -> None:
    order, h = _walkin(client, staff_headers, catalog)
    client.post(f"{S}/orders/{order['id']}/slip", headers=h)
    second = client.post(f"{S}/orders/{order['id']}/slip", headers=h)
    assert "REPRINT 1" in _text(second.content)
    actions = [a.action for a in db.scalars(select(AuditLog).where(AuditLog.entity_id == order["id"]))]
    assert actions.count("order.slip_print") == 1 and actions.count("order.slip_reprint") == 1
    detail = client.get(f"{S}/orders/{order['id']}", headers=h).json()
    assert detail["slip_print_count"] == 2
