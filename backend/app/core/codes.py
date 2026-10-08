"""Universal Order Code (ROADMAP §4.1).

    YYMMDD-NNNNN-C    e.g. 260924-00182-7
    date issued (Dhaka) · daily serial 00001–89999 (90000–99999 reserved for downtime blocks)
    · Damm check digit over the 11 digits.

Stored canonically as 12 digits, displayed with dashes. Tube accession = code + 2-digit tube number.
"""

from __future__ import annotations

import re
from datetime import date

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.errors import AppError, Invalid

# Damm quasigroup table (order 10, weakly totally anti-symmetric).
_DAMM = (
    (0, 3, 1, 7, 5, 9, 8, 6, 4, 2),
    (7, 0, 9, 2, 1, 5, 4, 8, 6, 3),
    (4, 2, 0, 6, 8, 7, 1, 3, 5, 9),
    (1, 7, 5, 0, 9, 8, 3, 4, 2, 6),
    (6, 1, 2, 3, 0, 4, 5, 9, 7, 8),
    (3, 6, 7, 4, 2, 0, 9, 5, 8, 1),
    (5, 8, 6, 9, 7, 2, 0, 1, 3, 4),
    (8, 9, 4, 5, 3, 6, 2, 0, 1, 7),
    (9, 4, 3, 8, 6, 1, 7, 2, 0, 5),
    (2, 5, 8, 1, 4, 3, 6, 7, 9, 0),
)

MAX_NORMAL_SERIAL = 89_999
DOWNTIME_SERIAL_START = 90_000
DOWNTIME_SERIAL_END = 99_999

_STRIP = re.compile(r"[\s\-–—]")


def damm_check(digits: str) -> int:
    """Return the Damm check digit for a string of decimal digits."""
    interim = 0
    for ch in digits:
        if not ch.isdigit():
            raise ValueError(f"not a digit: {ch!r}")
        interim = _DAMM[interim][int(ch)]
    return interim


def damm_valid(digits_with_check: str) -> bool:
    return digits_with_check.isdigit() and damm_check(digits_with_check) == 0


def make_code(issue_date: date, serial: int) -> str:
    if not 1 <= serial <= DOWNTIME_SERIAL_END:
        raise ValueError("serial out of range")
    body = f"{issue_date:%y%m%d}{serial:05d}"
    return f"{body}{damm_check(body)}"


def format_order_code(canonical: str) -> str:
    """'260924001827' -> '260924-00182-7'."""
    return f"{canonical[:6]}-{canonical[6:11]}-{canonical[11]}"


class CodeMistyped(AppError):
    status_code = 422

    def __init__(self) -> None:
        super().__init__("CODE_MISTYPED", "errors.code_mistyped")


def parse_order_code(value: str) -> str:
    """Accept '260924-00182-7', '260924001827', with spaces; return the canonical 12 digits.

    A 14-digit tube accession is also accepted and reduced to its order code.
    Raises CodeMistyped ("code mistyped") on wrong length or a bad check digit.
    """
    digits = _STRIP.sub("", value or "")
    if len(digits) == 14 and digits.isdigit():
        digits = digits[:12]
    if len(digits) != 12 or not digits.isdigit() or not damm_valid(digits):
        raise CodeMistyped()
    month, day = int(digits[2:4]), int(digits[4:6])
    if not (1 <= month <= 12 and 1 <= day <= 31):
        raise CodeMistyped()
    return digits


def is_downtime_code(canonical: str) -> bool:
    return int(canonical[6:11]) >= DOWNTIME_SERIAL_START


def tube_accession(order_code: str, n: int) -> str:
    """Code + 2-digit tube number, e.g. '26092400182701' (Code128-C friendly, 14 digits)."""
    if not 1 <= n <= 99:
        raise ValueError("tube number out of range")
    return f"{order_code}{n:02d}"


def parse_accession(value: str) -> str:
    digits = _STRIP.sub("", value or "")
    if len(digits) != 14 or not digits.isdigit() or not damm_valid(digits[:12]):
        raise Invalid("ACCESSION_MISTYPED")
    return digits


def format_accession(acc: str) -> str:
    return f"{format_order_code(acc[:12])} · T{acc[12:]}"


def next_counter(session: Session, key: str, start: int = 1) -> int:
    """Atomic counter (`INSERT … ON CONFLICT DO UPDATE … RETURNING`). Gaps are acceptable."""
    value = session.execute(
        text(
            "INSERT INTO daily_counter (key, value) VALUES (:key, :start) "
            "ON CONFLICT (key) DO UPDATE SET value = daily_counter.value + 1 "
            "RETURNING value"
        ),
        {"key": key, "start": start},
    ).scalar_one()
    return int(value)


def generate_order_code(session: Session, issue_date: date) -> str:
    serial = next_counter(session, f"order:{issue_date.isoformat()}")
    if serial > MAX_NORMAL_SERIAL:
        raise AppError("DAILY_CODE_CAPACITY_EXHAUSTED", status_code=503)
    return make_code(issue_date, serial)
