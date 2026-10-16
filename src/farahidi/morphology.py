"""Build the public morphological model from the port's raw records.

The AlKhalil port (:mod:`farahidi.analyzer`) produces one record per
*(morphological reading × إعراب ending)* — the Java ``Result`` layout, where
``عندليب`` comes out five times differing only in the case vowel. This module
holds the pieces that turn those records into :class:`~farahidi.models.Analysis`
objects: decoding the lexicon's part-of-speech labels and collapsing the records
over their inflections.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import replace
from typing import TYPE_CHECKING

from .models import Analysis, Inflection

if TYPE_CHECKING:
    from .analyzer import RawAnalysis

# Label sets used to decode the tool-word / proper-noun POS strings, whose
# pipe-separated slots are positional but irregular ("اسم|إشارة|مؤنث|جمع",
# "اسم|ضمير|الغائب", "فعل|ماض|جامد", "اسم|فعل|ماض" …).
_TENSES = frozenset({"ماض", "مضارع", "أمر"})
_GENDERS = frozenset({"مذكر", "مؤنث", "مذكر أو مؤنث"})
_NUMBERS = frozenset({"مفرد", "مثنى", "جمع"})
# Tool-word pronouns spell the person with the article; align with the verb labels.
_PERSONS = {"الغائب": "غائب", "المتكلم": "متكلم", "المخاطب": "مخاطب"}
# Single-slot labels that are not a bare part of speech.
_SINGLE_SLOT = {"اسم الجلالة": ("اسم", "اسم الجلالة"), "جار ومجرور": ("حرف", "جار ومجرور")}


def parse_pos_label(label: str) -> dict[str, str | None]:
    """Decode a tool-word style POS label into ``pos``/``type``/``tense``/
    ``gender``/``number``/``person`` (missing slots → ``None``)."""
    slots = label.split("|")
    out: dict[str, str | None] = {
        "pos": slots[0],
        "type": None,
        "tense": None,
        "gender": None,
        "number": None,
        "person": None,
    }
    if len(slots) == 1 and slots[0] in _SINGLE_SLOT:
        out["pos"], out["type"] = _SINGLE_SLOT[slots[0]]
    for slot in slots[1:]:
        if not slot or slot == "-":
            continue
        if slot in _TENSES and out["tense"] is None:
            out["tense"] = slot
        elif slot in _GENDERS and out["gender"] is None:
            out["gender"] = slot
        elif slot in _NUMBERS and out["number"] is None:
            out["number"] = slot
        elif slot in _PERSONS and out["person"] is None:
            out["person"] = _PERSONS[slot]
        elif out["type"] is None:
            out["type"] = slot
    return out


def collapse(raws: Iterable[RawAnalysis]) -> list[Analysis]:
    """Group raw records by morphological reading and nest their inflections.

    Records sharing the same reading (everything except the إعراب ending, the
    definiteness state and the score) become one :class:`Analysis` whose
    ``inflections`` are the distinct realizations, best first, and whose ``score``
    is the best inflection's. The result is sorted by ``score`` descending; ties
    keep the analyzer's pipeline order.
    """
    groups: dict[Analysis, dict[tuple, Inflection]] = {}
    for raw in raws:
        bucket = groups.setdefault(raw.morph, {})
        infl = raw.inflection
        key = (infl.diacritized, infl.case, infl.mood, infl.state)
        prev = bucket.get(key)
        if prev is None or prev.score < infl.score:
            bucket[key] = infl
    out: list[Analysis] = []
    for morph, bucket in groups.items():
        inflections = sorted(bucket.values(), key=lambda i: i.score, reverse=True)
        out.append(replace(morph, score=inflections[0].score, inflections=tuple(inflections)))
    out.sort(key=lambda a: a.score, reverse=True)
    return out
