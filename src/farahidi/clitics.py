"""Clitic segmentation — port of ``ProcliticImpl``/``EncliticImpl``/``Stemming``.

Enumerates every ``proclitic + stem + enclitic`` split of the unvoweled word,
gated by clitic compatibility classes. The proclitic/enclitic lists are built in
ascending-length order and share a single ``valid`` short-circuit flag exactly as
in ``Stemming.getListsSegment`` — this ordering quirk affects which segments are
produced, so it is reproduced faithfully.
"""

from __future__ import annotations

from .lexicon import Lexicon
from .normalize import is_definit

MAX_PROCLITIC = 5
MAX_ENCLITIC = 5


class Clitic:
    """A proclitic or enclitic. Mutable: ``voweledform`` is recomputed in
    context by the analyzers (e.g. هـ → هُ/هِ), matching the Java DTO."""

    __slots__ = ("unvoweledform", "voweledform", "desc", "classe")

    def __init__(self, unvoweledform: str, voweledform: str, desc: str, classe: str):
        self.unvoweledform = unvoweledform
        self.voweledform = voweledform
        self.desc = desc
        self.classe = classe

    @classmethod
    def from_dict(cls, d: dict) -> Clitic:
        return cls(d["unvoweledform"], d["voweledform"], d.get("desc") or "", d["classe"])


class Segment:
    __slots__ = ("proclitic", "stem", "enclitic")

    def __init__(self, proclitic: Clitic, stem: str, enclitic: Clitic):
        self.proclitic = proclitic
        self.stem = stem
        self.enclitic = enclitic


def _proclitics(lex: Lexicon, token: str) -> list[Clitic]:
    out: list[Clitic] = []
    size = len(token)
    ip = 0
    while ip < size and ip <= MAX_PROCLITIC:
        for d in lex.proclitics(token[:ip]):
            out.append(Clitic.from_dict(d))
        ip += 1
    return out


def _enclitics(lex: Lexicon, token: str) -> list[Clitic]:
    out: list[Clitic] = []
    size = len(token)
    ip = 0
    while ip < size and ip <= MAX_ENCLITIC:
        for d in lex.enclitics(token[size - ip : size]):
            out.append(Clitic.from_dict(d))
        ip += 1
    return out


def _get_alternatives(stem: str, st: str, valid: bool, valid_suf: bool) -> str:
    if st == "ت":
        return (stem[:-1] + "ة") if valid else ""
    if st == "آ":
        return (stem[:-1] + "أى") if valid else ""
    if st == "ا":
        return (stem[:-1] + "ى") if valid else ""
    if st == "و":
        return (stem + "ا") if valid else ""
    if st in ("ئ", "ؤ"):
        return (stem[:-1] + "ء") if valid_suf else ""
    return ""


def _is_valid_segment(seg: Segment) -> bool:
    proc = seg.proclitic.classe
    enc = seg.enclitic.classe
    return (
        (not enc.startswith("V") or not proc.startswith("N"))
        and (not proc.startswith("V") or not enc.startswith("N"))
        and (not is_definit(proc) or seg.enclitic.unvoweledform == "")
    )


def get_lists_segment(lex: Lexicon, unvoweled_word: str) -> list[Segment]:
    """Port of ``Stemming.getListsSegment``."""
    result: list[Segment] = []
    procs = _proclitics(lex, unvoweled_word)
    encs = _enclitics(lex, unvoweled_word)
    valid = True
    wlen = len(unvoweled_word)
    for p in procs:
        for s in encs:
            if not valid:
                break
            if wlen - len(s.unvoweledform) - len(p.unvoweledform) >= 0:
                alternatives: set[str] = set()
                stem = unvoweled_word[len(p.unvoweledform) : wlen - len(s.unvoweledform)]
                alternatives.add(stem)
                if (
                    p.classe in ("N1", "N2", "N3", "N5")
                    and p.unvoweledform.endswith("ل")
                    and not stem.startswith("ل")
                ):
                    alternatives.add("ل" + stem)
                if s.unvoweledform == "ي" and not stem.startswith("ي"):
                    alternatives.add(stem + "ي")
                if (
                    p.classe in ("N4", "C3")
                    and p.unvoweledform.endswith("ل")
                    and stem.startswith("ل")
                ):
                    alternatives.add(
                        _get_alternatives(
                            stem,
                            stem[-1],
                            len(s.unvoweledform) != 0,
                            len(s.unvoweledform) > 0,
                        )
                    )
                    stem = "ا" + stem
                alternatives.add(stem)
                if p.unvoweledform in ("أ", "ب"):
                    alternatives.add("ا" + stem)
                stem1 = ""
                if len(stem) > 1:
                    stem1 = _get_alternatives(
                        stem, stem[-1], len(s.unvoweledform) != 0, len(s.unvoweledform) > 0
                    )
                if stem1 != "":
                    alternatives.add(stem1)
                stem3 = stem1.replace("آ", "ءا")
                if stem3 != stem1:
                    alternatives.add(stem3)
                stem2 = stem.replace("آ", "ءا")
                if stem2 != stem:
                    alternatives.add(stem2)
                for sch in alternatives:
                    seg = Segment(p, sch, s)
                    if _is_valid_segment(seg):
                        result.append(seg)
            else:
                valid = False
    return result
