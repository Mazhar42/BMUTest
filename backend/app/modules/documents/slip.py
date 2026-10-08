"""The 3-part slip (ROADMAP §4.2): one A4 page cut into PATIENT / BANK / HOSPITAL copies, each carrying the
same order code — QR on the patient copy, Code128 on the bank and hospital copies. Reprints are
watermarked "REPRINT n"."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.core import clock, codes, settings_store
from app.modules.catalog.models import LabTest
from app.modules.documents import barcodes, words
from app.modules.identity import service as identity
from app.modules.orders.models import LabOrder, OrderStatus
from app.modules.patients import service as patients
from app.modules.prescriptions.models import Prescription

TEMPLATES = Path(__file__).resolve().parent / "templates"
_BN = str.maketrans("0123456789", "০১২৩৪৫৬৭৮৯")


@lru_cache
def _env() -> Environment:
    env = Environment(loader=FileSystemLoader(TEMPLATES), autoescape=select_autoescape(["html"]))
    env.filters["taka"] = lambda paisa: f"{paisa // 100:,}" + (f".{paisa % 100:02d}" if paisa % 100 else "")
    env.filters["bn"] = lambda s: str(s).translate(_BN)
    return env


def html_to_pdf(html: str) -> bytes:
    from weasyprint import HTML  # imported lazily: needs Pango (present in the Docker image)

    pdf: bytes = HTML(string=html, base_url=str(TEMPLATES)).write_pdf()
    return pdf


def slip_context(db: Session, order: LabOrder, reprint: int) -> dict[str, Any]:
    s = get_settings()
    assert order.order_code is not None
    patient = patients.get(db, order.patient_id)
    items = order.active_items
    tests = {t.id: t for t in db.scalars(select(LabTest).where(LabTest.id.in_([i.test_id for i in items])))}
    prep: list[dict[str, Any]] = []
    for i in items:
        t = tests.get(i.test_id)
        if t is None:
            continue
        if t.fasting_required or t.prep_en or t.prep_bn:
            prep.append(
                {
                    "abbr": i.abbreviation,
                    "fasting_hours": t.fasting_hours if t.fasting_required else None,
                    "en": t.prep_en,
                    "bn": t.prep_bn,
                }
            )
    prescription = db.get(Prescription, order.prescription_id) if order.prescription_id else None
    paid = order.status not in (OrderStatus.AWAITING_PAYMENT, OrderStatus.PENDING_VERIFICATION)
    return {
        "order": order,
        "code": codes.format_order_code(order.order_code),
        "code_raw": order.order_code,
        "patient": patient,
        "age": patient.age,
        "items": items,
        "prep": prep,
        "prescription": prescription,
        "verified_by": identity.staff_name(db, order.verified_by_staff_id),
        "waiver_by": identity.staff_name(db, order.waiver_approved_by),
        "paid": paid,
        "show_bank_copy": not paid or settings_store.get_bool(db, "print_bank_copy_when_paid"),
        "amount_words_en": words.taka_in_words(order.total, "en"),
        "amount_words_bn": words.taka_in_words(order.total, "bn"),
        "qr": barcodes.qr_data_uri(order.order_code),
        "barcode": barcodes.code128_data_uri(order.order_code),
        "reprint": reprint,
        "printed_at": clock.local_now(),
        "institution_en": s.institution_name_en,
        "institution_bn": s.institution_name_bn,
        "lab_en": s.lab_name_en,
        "lab_bn": s.lab_name_bn,
        "address": s.institution_address,
        "account_head": s.slip_account_head,
        "portal": s.public_base_url,
    }


def render_slip_html(db: Session, order: LabOrder, reprint: int = 0) -> str:
    return _env().get_template("slip.html").render(**slip_context(db, order, reprint))


def render_slip(db: Session, order: LabOrder, reprint: int = 0) -> bytes:
    return html_to_pdf(render_slip_html(db, order, reprint))
