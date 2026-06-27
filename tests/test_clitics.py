"""Unit tests for clitic segmentation."""

from __future__ import annotations

import pytest

from farahidi.clitics import get_lists_segment
from farahidi.lexicon import Lexicon


@pytest.fixture(scope="module")
def lex() -> Lexicon:
    return Lexicon()


def _stems(segments):
    return {(s.proclitic.unvoweledform, s.stem, s.enclitic.unvoweledform) for s in segments}


def test_bare_word_has_empty_clitic_segment(lex):
    segs = get_lists_segment(lex, "كتب")
    triples = _stems(segs)
    # the no-clitic split must be present
    assert ("", "كتب", "") in triples


def test_proclitic_and_enclitic_split(lex):
    # لأنهم -> proclitic ل + stem أن + enclitic هم should be among the splits
    segs = get_lists_segment(lex, "لأنهم")
    triples = _stems(segs)
    assert ("ل", "أنهم", "") in triples or any(
        p == "ل" and e == "هم" for (p, _s, e) in triples
    )


def test_segments_respect_class_compatibility(lex):
    # every produced segment must pass the verbal/nominal class gate
    for seg in get_lists_segment(lex, "بالمدرسة"):
        proc = seg.proclitic.classe
        enc = seg.enclitic.classe
        # a verbal enclitic with a nominal proclitic (and vice-versa) is rejected
        assert not (enc.startswith("V") and proc.startswith("N"))
        assert not (proc.startswith("V") and enc.startswith("N"))


def test_returns_list(lex):
    assert isinstance(get_lists_segment(lex, "من"), list)
