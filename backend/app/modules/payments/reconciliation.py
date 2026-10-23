"""Bank-statement reconciliation (ROADMAP M4): upload a CSV with a per-bank column mapping, auto-match
lines to teller payments by order code (or receipt number) and amount, and list the exceptions."""

from __future__ import annotations

import csv
import hashlib
import io
import re
import uuid
from collections import Counter
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core import audit, codes
from app.core.actor import Actor
from app.core.errors import Conflict, Invalid, NotFound
from app.modules.orders.models import LabOrder
from app.modules.payments.models import (
    BankColumnMapping,
    BankStatementImport,
    BankStatementLine,
    LineMatch,
    Payment,
    PaymentMethod,
    PaymentStatus,
    ReconciliationStatus,
)

_CODE = re.compile(r"(?<!\d)(\d{6})[-\s]?(\d{5})[-\s]?(\d)(?!\d)")
MATCHABLE = (PaymentStatus.SUCCESS, PaymentStatus.REFUND_PENDING, PaymentStatus.REFUNDED)
EXCEPTIONS = (LineMatch.UNMATCHED, LineMatch.AMOUNT_MISMATCH, LineMatch.DUPLICATE)


def extract_order_code(text: str) -> str | None:
    """Find a valid order code (check digit verified) anywhere in a bank reference."""
    for m in _CODE.finditer(text or ""):
        try:
            return codes.parse_order_code("".join(m.groups()))
        except codes.CodeMistyped:
            continue
    return None


def _amount(raw: str) -> int | None:
    cleaned = re.sub(r"[^\d.\-]", "", (raw or "").replace(",", ""))
    if not cleaned:
        return None
    try:
        return int((Decimal(cleaned) * 100).to_integral_value())
    except InvalidOperation:
        return None


def _date(raw: str, fmt: str) -> date | None:
    try:
        return datetime.strptime((raw or "").strip(), fmt).date()
    except ValueError:
        return None


def save_mapping(
    db: Session,
    bank_name: str,
    date_column: str,
    amount_column: str,
    reference_column: str,
    receipt_column: str | None,
    date_format: str,
) -> BankColumnMapping:
    m = db.scalar(select(BankColumnMapping).where(BankColumnMapping.bank_name == bank_name))
    if m is None:
        m = BankColumnMapping(id=uuid.uuid4(), bank_name=bank_name)
        db.add(m)
    m.date_column, m.amount_column, m.reference_column = date_column, amount_column, reference_column
    m.receipt_column, m.date_format = receipt_column or None, date_format
    return m


def match_line(db: Session, line: BankStatementLine) -> None:
    """Set `line.match` (and the payment's reconciliation status) from the current payments."""
    candidates: list[Payment] = []
    if line.order_code:
        order_id = db.scalar(select(LabOrder.id).where(LabOrder.order_code == line.order_code))
        if order_id is not None:
            candidates = list(
                db.scalars(
                    select(Payment).where(
                        Payment.order_id == order_id,
                        Payment.method == PaymentMethod.BANK_TELLER,
                        Payment.status.in_(MATCHABLE),
                    )
                )
            )
    elif line.receipt_no:
        candidates = list(
            db.scalars(
                select(Payment).where(
                    Payment.bank_receipt_no == line.receipt_no,
                    Payment.method == PaymentMethod.BANK_TELLER,
                    Payment.status.in_(MATCHABLE),
                )
            )
        )
    if not candidates:
        line.match = LineMatch.UNMATCHED
        line.note = (
            "No teller payment recorded for this reference yet" if line.order_code else "No order code in the reference"
        )
        return
    exact = [p for p in candidates if p.amount == line.amount]
    if not exact:
        line.match = LineMatch.AMOUNT_MISMATCH
        line.note = (
            "Recorded " + ", ".join(f"{p.amount / 100:.2f}" for p in candidates) + f" · bank {line.amount / 100:.2f}"
        )
        for p in candidates:
            p.reconciliation_status = ReconciliationStatus.EXCEPTION.value
            p.reconciliation_note = f"bank amount {line.amount / 100:.2f}"
        return
    payment = exact[0]
    taken = db.scalar(
        select(BankStatementLine.id).where(
            BankStatementLine.matched_payment_id == payment.id, BankStatementLine.id != line.id
        )
    )
    if taken is not None:
        line.match = LineMatch.DUPLICATE
        line.note = "Another bank line already matched this payment"
        return
    line.match = LineMatch.MATCHED
    line.matched_payment_id = payment.id
    line.note = None
    payment.reconciliation_status = ReconciliationStatus.MATCHED.value
    payment.reconciliation_note = None


def import_statement(
    db: Session, text: str, filename: str, mapping: BankColumnMapping, actor: Actor
) -> BankStatementImport:
    reader = csv.DictReader(io.StringIO(text))
    headers = {(h or "").strip().lower(): h for h in (reader.fieldnames or [])}
    needed = [mapping.date_column, mapping.amount_column, mapping.reference_column]
    missing = [c for c in needed if c.strip().lower() not in headers]
    if missing:
        raise Invalid("CSV_COLUMNS_MISSING", columns=missing, found=list(reader.fieldnames or []))

    def cell(row: dict[str, str], column: str | None) -> str:
        key = headers.get((column or "").strip().lower())
        return (row.get(key) or "").strip() if key else ""

    imp = BankStatementImport(
        id=uuid.uuid4(), bank_name=mapping.bank_name, filename=filename[:200], uploaded_by=actor.id
    )
    db.add(imp)
    db.flush()
    seen: Counter[str] = Counter()
    for line_no, row in enumerate(reader, start=2):
        imp.rows += 1
        amount = _amount(cell(row, mapping.amount_column))
        if amount is None or amount <= 0:  # debits, balances, blanks
            imp.skipped += 1
            continue
        reference = cell(row, mapping.reference_column)
        receipt = cell(row, mapping.receipt_column) or None
        txn_date = _date(cell(row, mapping.date_column), mapping.date_format)
        content = "|".join([mapping.bank_name, str(txn_date), str(amount), reference, receipt or ""])
        seen[content] += 1
        fingerprint = hashlib.sha256(f"{content}|{seen[content]}".encode()).hexdigest()
        if db.scalar(
            select(BankStatementLine.id).where(
                BankStatementLine.bank_name == mapping.bank_name, BankStatementLine.fingerprint == fingerprint
            )
        ):
            imp.skipped += 1  # the same line from an earlier (overlapping) statement
            continue
        line = BankStatementLine(
            id=uuid.uuid4(),
            import_id=imp.id,
            bank_name=mapping.bank_name,
            fingerprint=fingerprint,
            line_no=line_no,
            txn_date=txn_date,
            amount=amount,
            reference=reference,
            receipt_no=receipt,
            order_code=extract_order_code(reference),
            match=LineMatch.UNMATCHED,
            raw={k: v for k, v in row.items() if k},
        )
        db.add(line)
        db.flush()
        match_line(db, line)
        if line.match == LineMatch.MATCHED:
            imp.matched += 1
        else:
            imp.exceptions += 1
    audit.record(
        db,
        actor,
        "reconciliation.import",
        entity_type="bank_statement_import",
        entity_id=imp.id,
        after={"bank": mapping.bank_name, "rows": imp.rows, "matched": imp.matched, "exceptions": imp.exceptions},
    )
    return imp


def rematch_open_lines(db: Session) -> dict[str, int]:
    """Nightly: lines that were UNMATCHED may match payments recorded since (e.g. back-entered receipts)."""
    lines = list(db.scalars(select(BankStatementLine).where(BankStatementLine.match == LineMatch.UNMATCHED)))
    matched = 0
    for line in lines:
        match_line(db, line)
        matched += line.match == LineMatch.MATCHED
    return {"checked": len(lines), "matched": matched}


def exceptions(db: Session, limit: int = 300) -> list[BankStatementLine]:
    return list(
        db.scalars(
            select(BankStatementLine)
            .where(BankStatementLine.match.in_(EXCEPTIONS))
            .order_by(BankStatementLine.created_at.desc(), BankStatementLine.line_no)
            .limit(limit)
        )
    )


def resolve(db: Session, line_id: uuid.UUID, note: str, actor: Actor) -> BankStatementLine:
    line = db.get(BankStatementLine, line_id, with_for_update=True)
    if line is None:
        raise NotFound("bank_statement_line")
    if line.match not in EXCEPTIONS:
        raise Conflict("LINE_NOT_AN_EXCEPTION", match=line.match.value)
    before = line.match.value
    line.match = LineMatch.RESOLVED
    line.note = note.strip()
    line.resolved_by = actor.id
    audit.record(
        db,
        actor,
        "reconciliation.resolve",
        entity_type="bank_statement_line",
        entity_id=line.id,
        before={"match": before},
        after={"note": line.note},
    )
    return line
