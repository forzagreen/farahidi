"""``ArabicStringUtil.Vowelize`` — reconstruct the fully voweled surface word
from a stem + diacritic pattern + clitics. Mutates the segment's enclitic
``voweledform`` in context (هـ → هُ/هِ etc.), as in the Java reference.
"""

from __future__ import annotations

import re

from .clitics import Segment
from .normalize import (
    add_diac_before_string,
    correct_hamza,
    get_diacritization_stem,
    is_definit,
    is_diacritic,
    is_solar,
)

_V4_END_RE = re.compile("[ًٌٍَُِْ]$")


def vowelize(segment: Segment, pattern: str) -> list[str]:
    proc_class = segment.proclitic.classe
    enc = segment.enclitic
    stem = segment.stem

    if enc.classe == "V4":
        pattern = _V4_END_RE.sub("ُ", pattern)

    result = get_diacritization_stem(pattern, stem)
    result = (
        result[0]
        + ("ّ" if (is_definit(proc_class) and is_solar(stem[0])) else "")
        + result[1:]
    )
    soukoun = "ْ" if (is_definit(proc_class) and not is_solar(stem[0])) else ""

    if enc.voweledform != "":
        result = result.replace("ة", "ت")
    if (result.endswith("ُوا") or result.endswith("وْا")) and enc.unvoweledform != "":
        result = result[:-1]

    ends_i = result.endswith("ي") or result.endswith("يْ") or result.endswith("ِ")
    if enc.unvoweledform == "ه":
        enc.voweledform = "هِ" if ends_i else "هُ"
    if enc.unvoweledform == "هما":
        enc.voweledform = "هِمَا" if ends_i else "هُمَا"
    if enc.unvoweledform == "هم":
        enc.voweledform = "هِمْ" if ends_i else "هُمْ"
    if enc.unvoweledform == "هن":
        enc.voweledform = "هِنَّ" if ends_i else "هُنَّ"

    if result[-1] in ("ُ", "َ") and enc.unvoweledform == "ي":
        result = result[:-1] + "ِ"

    enc_voweled = enc.voweledform
    if len(enc_voweled) > 0:
        result = result.replace("ى", "ا")
        if (not result.endswith("يْ") or enc.classe != "N1") and (
            result.endswith("ْ")
            or len(enc_voweled) == 1
            or not is_diacritic(enc_voweled[1])
        ):
            res = add_diac_before_string(enc_voweled, result)
        else:
            res = result + enc_voweled
    else:
        res = result

    if res != "":
        res = correct_hamza(res)

    head = (
        res[1:]
        if (
            segment.proclitic.unvoweledform == "أ"
            and len(res) > 3
            and res[0] == "ا"
            and res[2] == "ْ"
        )
        else res
    )
    resultat0 = segment.proclitic.voweledform + soukoun + head
    if resultat0.endswith("يْي") and enc.classe == "N1":
        # Replacement is ya + shadda + fatha (U+064A U+0651 U+064E), matching the
        # exact combining-mark order AlKhalil emits (not the NFC fatha+shadda order).
        resultat0 = re.sub("يْي$", "يَّ", resultat0)
    return [resultat0, result]
