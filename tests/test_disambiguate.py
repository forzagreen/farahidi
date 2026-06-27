"""Layer-2 parity tests: farahidi's in-context disambiguation must match the Java
``ADATAnalyzer`` per-token chosen lemma / stem / root.

The fixture ``sentences.jsonl`` is produced by ``tools/gen_golden.py --mode
sentences`` from the reference. Each record carries the exact token list the Java
tokenizer produced, so these tests isolate Layer-2 from tokenization: we feed
those tokens straight to the disambiguator.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from farahidi import Disambiguator

FIXTURE = Path(__file__).parent / "fixtures" / "sentences.jsonl"


def _load() -> list[dict]:
    with FIXTURE.open(encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


RECORDS = _load()
_DIS = Disambiguator()


def _cases():
    for rec in RECORDS:
        results = _DIS.disambiguate(rec["tokens"])
        got = {
            "lemmas": [r.lemma for r in results],
            "stems": [r.stem for r in results],
            "roots": [r.root for r in results],
        }
        for field in ("lemmas", "stems", "roots"):
            for idx, token in enumerate(rec["tokens"]):
                yield pytest.param(
                    rec[field][idx],
                    got[field][idx],
                    id=f"{rec['sentence']}::{field}[{idx}]={token}",
                )


@pytest.mark.parametrize(("expected", "actual"), list(_cases()))
def test_token_parity(expected: str, actual: str) -> None:
    assert actual == expected
