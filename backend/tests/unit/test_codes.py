from __future__ import annotations

from datetime import date

import pytest

from app.core.codes import (
    CodeMistyped,
    damm_check,
    damm_valid,
    format_order_code,
    generate_order_code,
    make_code,
    parse_order_code,
    tube_accession,
)


def test_damm_reference_vector() -> None:
    assert damm_check("572") == 4
    assert damm_valid("5724")


def test_make_and_format_code() -> None:
    code = make_code(date(2026, 9, 24), 182)
    assert len(code) == 12
    assert code.startswith("26092400182")
    assert damm_valid(code)
    assert format_order_code(code) == f"260924-00182-{code[-1]}"


@pytest.mark.parametrize("serial", [1, 182, 4567, 89999, 90001])
def test_round_trip_parse_format(serial: int) -> None:
    code = make_code(date(2026, 1, 31), serial)
    assert parse_order_code(format_order_code(code)) == code
    assert parse_order_code(code) == code
    assert parse_order_code(f"  {code[:6]} {code[6:11]} {code[11]} ") == code


def test_every_single_digit_mutation_is_rejected() -> None:
    code = make_code(date(2026, 9, 24), 182)
    for i in range(12):
        for d in "0123456789":
            if d == code[i]:
                continue
            mutated = code[:i] + d + code[i + 1 :]
            with pytest.raises(CodeMistyped):
                parse_order_code(mutated)


def test_every_adjacent_transposition_is_rejected() -> None:
    for serial in (182, 12345, 70001):
        code = make_code(date(2026, 9, 24), serial)
        for i in range(11):
            if code[i] == code[i + 1]:
                continue
            swapped = code[:i] + code[i + 1] + code[i] + code[i + 2 :]
            with pytest.raises(CodeMistyped):
                parse_order_code(swapped)


@pytest.mark.parametrize("bad", ["", "abc", "26092400182", "2609240018270", "26-09-24"])
def test_garbage_rejected(bad: str) -> None:
    with pytest.raises(CodeMistyped):
        parse_order_code(bad)


def test_accession_reduces_to_order_code() -> None:
    code = make_code(date(2026, 9, 24), 182)
    acc = tube_accession(code, 1)
    assert acc == code + "01"
    assert parse_order_code(acc) == code


def test_generate_order_code_is_sequential(db) -> None:  # type: ignore[no-untyped-def]
    d = date(2031, 5, 6)
    a = generate_order_code(db, d)
    b = generate_order_code(db, d)
    assert a[:6] == "310506"
    assert int(b[6:11]) == int(a[6:11]) + 1
    assert damm_valid(a) and damm_valid(b)
