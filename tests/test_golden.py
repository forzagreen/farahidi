"""Parity tests against the Java AlKhalil reference.

``tests/fixtures/golden.jsonl`` holds, per word, every analysis produced by the
original ``AlKhalil2Analyzer.processToken`` (12 fields each). We require the
Python port to reproduce the exact same multiset of analyses, and that the
top-ranked candidate matches after sorting by ``priority``.
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

import pytest

import farahidi

FIXTURE = Path(__file__).parent / "fixtures" / "golden.jsonl"

# golden JSON key -> Analysis attribute
KEYMAP = {
    "voweledWord": "voweled_word",
    "proclitic": "proclitic",
    "stem": "stem",
    "partOfSpeech": "part_of_speech",
    "diacPatternStem": "diac_pattern_stem",
    "patternStem": "pattern_stem",
    "lemma": "lemma",
    "patternLemma": "pattern_lemma",
    "root": "root",
    "caseOrMood": "case_or_mood",
    "enclitic": "enclitic",
    "priority": "priority",
}


def _load_golden():
    cases = []
    with FIXTURE.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                rec = json.loads(line)
                cases.append((rec["word"], rec["analyses"]))
    return cases


GOLDEN = _load_golden()


def _gtuple(a: dict) -> tuple:
    return tuple(a[k] for k in KEYMAP)


def _ptuple(a: farahidi.Analysis) -> tuple:
    return tuple(getattr(a, v) for v in KEYMAP.values())


@pytest.fixture(scope="module")
def analyzer() -> farahidi.Analyzer:
    return farahidi.Analyzer()


@pytest.mark.parametrize("word,analyses", GOLDEN, ids=[w for w, _ in GOLDEN])
def test_multiset_matches_reference(analyzer, word, analyses):
    expected = Counter(_gtuple(a) for a in analyses)
    got = Counter(_ptuple(a) for a in analyzer.process_token(word))
    assert got == expected


@pytest.mark.parametrize("word,analyses", GOLDEN, ids=[w for w, _ in GOLDEN])
def test_top_ranked_matches_reference(analyzer, word, analyses):
    """The highest-priority analysis must be reproduced. The reference fixture
    is unsorted, so we compare against the max-priority entry there."""
    if not analyses:
        pytest.skip("no analyses")
    best_priority = max(a["priority"] for a in analyses)
    expected_best = {_gtuple(a) for a in analyses if a["priority"] == best_priority}
    ranked = analyzer.analyze(word)
    assert ranked, f"no analyses for {word}"
    assert _ptuple(ranked[0]) in expected_best


def test_golden_fixture_nonempty():
    assert len(GOLDEN) >= 25
