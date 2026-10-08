from __future__ import annotations

import pytest

from app.modules.documents.words import taka_in_words


@pytest.mark.parametrize(
    ("paisa", "en", "bn"),
    [
        (0, "Zero taka only", "শূন্য টাকা মাত্র"),
        (15000, "One hundred fifty taka only", "একশত পঞ্চাশ টাকা মাত্র"),
        (125050, "One thousand two hundred fifty taka and fifty paisa only", "এক হাজার দুইশত পঞ্চাশ টাকা পঞ্চাশ পয়সা মাত্র"),
        (
            1234567800,
            "One crore twenty-three lakh forty-five thousand six hundred seventy-eight taka only",
            "এক কোটি তেইশ লক্ষ পঁয়তাল্লিশ হাজার ছয়শত আটাত্তর টাকা মাত্র",
        ),
    ],
)
def test_taka_in_words(paisa: int, en: str, bn: str) -> None:
    assert taka_in_words(paisa, "en") == en
    assert taka_in_words(paisa, "bn") == bn
