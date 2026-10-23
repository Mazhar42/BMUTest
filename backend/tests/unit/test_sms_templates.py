"""Every SMS template fits in 2 segments with realistic worst-case values (ROADMAP §9, §12)."""

from __future__ import annotations

import pytest

from app.modules.notifications import service

WORST = {
    "otp": "999999",
    "code": "261231-89999-9",
    "amount": "12,34,567",
    "link": "https://lab.bsmmu.edu.bd/o/261231899999",
    "token": "P-1234",
}


def test_bn_and_en_have_the_same_templates() -> None:
    assert set(service.templates("bn")) == set(service.templates("en"))


@pytest.mark.parametrize("lang", ["bn", "en"])
@pytest.mark.parametrize("key", sorted(service.templates("en")))
def test_template_fits_two_segments(lang: str, key: str) -> None:
    params = {**WORST, "amount": service.money_text(123456700, lang)}
    body = service.render(key, lang, params)
    assert "{" not in body
    assert service.sms_segments(body) <= 2, f"{lang}/{key}: {len(body)} chars"


def test_segment_maths() -> None:
    assert service.sms_segments("a" * 160) == 1
    assert service.sms_segments("a" * 161) == 2
    assert service.sms_segments("আ" * 70) == 1
    assert service.sms_segments("আ" * 71) == 2
    assert service.sms_segments("আ" * 134) == 2


def test_money_text_uses_language_numerals() -> None:
    assert service.money_text(125000, "en") == "1,250"
    assert service.money_text(125000, "bn") == "১,২৫০"
    assert service.money_text(125050, "en") == "1,250.50"
