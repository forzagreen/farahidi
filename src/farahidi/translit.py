"""Buckwalter⇄Arabic transliteration.

A faithful port of AlKhalil's ``util/Transliteration`` +
``util/ArabicCharacterUtil`` character tables. Only needed to read the Layer-2
language model (``*.lm``), which stores tokens in Buckwalter while every other
table — and farahidi's whole internal representation — is Arabic script.

Characters absent from the table pass through unchanged, exactly as the Java
``getArabicCharacter`` / ``getBuckWalterCharacter`` ``switch`` statements fall
through to ``return c``.
"""

from __future__ import annotations

# Buckwalter char -> Arabic char, transcribed verbatim from
# ArabicCharacterUtil.getArabicCharacter. The table is a bijection, so the
# Arabic -> Buckwalter direction is just its inverse.
_BW_TO_AR: dict[str, str] = {
    "'": "ء",
    "|": "آ",
    ">": "أ",
    "&": "ؤ",
    "<": "إ",
    "}": "ئ",
    "A": "ا",
    "b": "ب",
    "p": "ة",
    "t": "ت",
    "v": "ث",
    "j": "ج",
    "H": "ح",
    "x": "خ",
    "d": "د",
    "*": "ذ",
    "r": "ر",
    "z": "ز",
    "s": "س",
    "$": "ش",
    "S": "ص",
    "D": "ض",
    "T": "ط",
    "Z": "ظ",
    "E": "ع",
    "g": "غ",
    "_": "ـ",
    "f": "ف",
    "q": "ق",
    "k": "ك",
    "l": "ل",
    "m": "م",
    "n": "ن",
    "h": "ه",
    "w": "و",
    "Y": "ى",
    "y": "ي",
    "F": "ً",
    "N": "ٌ",
    "K": "ٍ",
    "a": "َ",
    "u": "ُ",
    "i": "ِ",
    "~": "ّ",
    "o": "ْ",
    "`": "ٰ",
    "{": "ٱ",
    "P": "پ",
    "J": "چ",
    "V": "ڤ",
    "G": "گ",
    "R": "ژ",
    ",": "،",
    ";": "؛",
    "?": "؟",
}

_AR_TO_BW: dict[str, str] = {ar: bw for bw, ar in _BW_TO_AR.items()}


def bw_to_arabic(word: str) -> str:
    """Port of ``Transliteration.getBuckWalterToArabic``."""
    return "".join(_BW_TO_AR.get(c, c) for c in word)


def arabic_to_bw(word: str) -> str:
    """Port of ``Transliteration.getArabicToBuckWalter``."""
    return "".join(_AR_TO_BW.get(c, c) for c in word)
