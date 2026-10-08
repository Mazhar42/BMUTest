"""Amount in words for the bank copy (ROADMAP §4.2), South-Asian grouping (crore / lakh / thousand)."""

from __future__ import annotations

_EN_ONES = [
    "zero",
    "one",
    "two",
    "three",
    "four",
    "five",
    "six",
    "seven",
    "eight",
    "nine",
    "ten",
    "eleven",
    "twelve",
    "thirteen",
    "fourteen",
    "fifteen",
    "sixteen",
    "seventeen",
    "eighteen",
    "nineteen",
]
_EN_TENS = ["_", "_", "twenty", "thirty", "forty", "fifty", "sixty", "seventy", "eighty", "ninety"]

# Bangla has an irregular word for every number 0–99.
_BN_0_99 = [
    "শূন্য",
    "এক",
    "দুই",
    "তিন",
    "চার",
    "পাঁচ",
    "ছয়",
    "সাত",
    "আট",
    "নয়",
    "দশ",
    "এগারো",
    "বারো",
    "তেরো",
    "চৌদ্দ",
    "পনেরো",
    "ষোলো",
    "সতেরো",
    "আঠারো",
    "উনিশ",
    "বিশ",
    "একুশ",
    "বাইশ",
    "তেইশ",
    "চব্বিশ",
    "পঁচিশ",
    "ছাব্বিশ",
    "সাতাশ",
    "আঠাশ",
    "উনত্রিশ",
    "ত্রিশ",
    "একত্রিশ",
    "বত্রিশ",
    "তেত্রিশ",
    "চৌত্রিশ",
    "পঁয়ত্রিশ",
    "ছত্রিশ",
    "সাঁইত্রিশ",
    "আটত্রিশ",
    "উনচল্লিশ",
    "চল্লিশ",
    "একচল্লিশ",
    "বিয়াল্লিশ",
    "তেতাল্লিশ",
    "চুয়াল্লিশ",
    "পঁয়তাল্লিশ",
    "ছেচল্লিশ",
    "সাতচল্লিশ",
    "আটচল্লিশ",
    "উনপঞ্চাশ",
    "পঞ্চাশ",
    "একান্ন",
    "বাহান্ন",
    "তিপ্পান্ন",
    "চুয়ান্ন",
    "পঞ্চান্ন",
    "ছাপ্পান্ন",
    "সাতান্ন",
    "আটান্ন",
    "উনষাট",
    "ষাট",
    "একষট্টি",
    "বাষট্টি",
    "তেষট্টি",
    "চৌষট্টি",
    "পঁয়ষট্টি",
    "ছেষট্টি",
    "সাতষট্টি",
    "আটষট্টি",
    "উনসত্তর",
    "সত্তর",
    "একাত্তর",
    "বাহাত্তর",
    "তিয়াত্তর",
    "চুয়াত্তর",
    "পঁচাত্তর",
    "ছিয়াত্তর",
    "সাতাত্তর",
    "আটাত্তর",
    "উনআশি",
    "আশি",
    "একাশি",
    "বিরাশি",
    "তিরাশি",
    "চুরাশি",
    "পঁচাশি",
    "ছিয়াশি",
    "সাতাশি",
    "আটাশি",
    "উননব্বই",
    "নব্বই",
    "একানব্বই",
    "বিরানব্বই",
    "তিরানব্বই",
    "চুরানব্বই",
    "পঁচানব্বই",
    "ছিয়ানব্বই",
    "সাতানব্বই",
    "আটানব্বই",
    "নিরানব্বই",
]
assert len(_BN_0_99) == 100

_SCALES = ((10_000_000, "crore", "কোটি"), (100_000, "lakh", "লক্ষ"), (1_000, "thousand", "হাজার"), (100, "hundred", "শত"))


def _en_below_100(n: int) -> str:
    if n < 20:
        return _EN_ONES[n]
    tens, ones = divmod(n, 10)
    return _EN_TENS[tens] + (f"-{_EN_ONES[ones]}" if ones else "")


def _words(n: int, lang: str) -> str:
    if n == 0:
        return _EN_ONES[0] if lang == "en" else _BN_0_99[0]
    parts: list[str] = []
    for value, en, bn in _SCALES:
        if n >= value:
            count, n = divmod(n, value)
            if lang == "en":
                parts.append(f"{_words(count, 'en')} {en}")
            else:  # Bangla writes hundreds closed up: দুইশত
                parts.append(f"{_words(count, 'bn')}{'' if value == 100 else ' '}{bn}")
    if n:
        parts.append(_en_below_100(n) if lang == "en" else _BN_0_99[n])
    return " ".join(parts)


def taka_in_words(paisa: int, lang: str) -> str:
    """12550 paisa -> 'One hundred twenty-five taka and fifty paisa only' / 'একশত পঁচিশ টাকা পঞ্চাশ পয়সা মাত্র'."""
    taka, ps = divmod(paisa, 100)
    if lang == "en":
        text = f"{_words(taka, 'en')} taka" + (f" and {_words(ps, 'en')} paisa" if ps else "") + " only"
        return text[0].upper() + text[1:]
    return f"{_words(taka, 'bn')} টাকা" + (f" {_words(ps, 'bn')} পয়সা" if ps else "") + " মাত্র"
