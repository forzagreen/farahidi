"""Layer-2 language model: the ``*.lm`` HMM tables + corpus frequency maps.

Ports the model side of ``ADATAnalyzer`` (``setAllMatrix`` /  ``setAllMatrixS``,
~L218 / L1138). The ``.lm`` is plain-text, length-prefixed, **Buckwalter**; every
key is converted to Arabic on load so the rest of farahidi stays Arabic-script.

Three matrices come out of the ``.lm``:

* **start**   ``{lemma -> (total, freq)}``      (the ``S0`` denominator + each ``S1``)
* **emission** ``{"unvWord:lemma" -> freq/wordFreq}``   (``B`` lines)
* **transition** ``{"lemma1:lemma2" -> freq2/freq1}``   (``A`` lines)

The three corpus maps are standard ``*.map`` tables (already exported to JSONL):
``mapLemma`` (Double backoff weight), ``mapStem`` / ``mapRoot`` (Long counts).

The whole model is parsed once and cached (≈ matching the constructor's
``setAllMatrixS`` which loads the entire ``.lm`` unfiltered; per-call prefiltering
in the Java CLI is only an optimisation and yields identical lookups).
"""

from __future__ import annotations

import gzip
from functools import cache
from importlib.resources import files

from . import translit
from .lexicon import load_map

LM_FILE = "DATA.MSA.ALL.TRAIN.141809.lm"
LM_ENCODING = "cp1252"  # what the Java reader uses; the content is pure ASCII

MAP_LEMMA = "DATA.MSA-LEMMA.ALL-train.map"  # backoff weights (float)
MAP_STEM = "DATA.MSA.SHA.STEM.map"  # stem corpus counts (int)
MAP_ROOT = "DATA.MSA.SHA.ROOT.map"  # root corpus counts (int)


def _data_dir():
    return files("farahidi") / "data"


@cache
def load_lm() -> tuple[dict[str, tuple[float, float]], dict[str, float], dict[str, float]]:
    """Parse the ``.lm`` into ``(start, emission, transition)`` dicts (cached).

    Byte-for-byte port of the ``setAllMatrix`` substring arithmetic, including
    the freq slices that capture a leading separator (``float`` strips it, as
    Java ``Double.parseDouble`` does).
    """
    start: dict[str, tuple[float, float]] = {}
    emission: dict[str, float] = {}
    transition: dict[str, float] = {}
    bw = translit.bw_to_arabic

    path = _data_dir() / (LM_FILE + ".gz")
    s_total = 0.0
    with gzip.open(path.open("rb"), "rt", encoding=LM_ENCODING, newline="") as fh:
        for raw in fh:
            line = raw.rstrip("\r\n")
            if not line:
                continue
            kind = line[0]
            if kind == "S":
                if line[1] == "1":
                    size = int(line[3:5])
                    tag = line[6 : 6 + size]
                    tag_freq = float(line[7 + size :])
                    start[bw(tag)] = (s_total, tag_freq)
                else:  # S0 <total>
                    s_total = float(line[3:])
            elif kind == "B":
                size_t = int(line[2:4])
                size_f = int(line[4:5])
                word = line[6 : 6 + size_t]
                word_freq = float(line[7 + size_t : 7 + size_t + size_f])
                word_ar = bw(word)
                pos = 8 + size_t + size_f
                n = len(line)
                while pos < n:
                    s2t = int(line[pos : pos + 2])
                    s2f = int(line[pos + 2 : pos + 3])
                    tag = line[pos + 4 : pos + 4 + s2t]
                    tag_freq = float(line[pos + 4 + s2t : pos + 5 + s2t + s2f])
                    emission[word_ar + ":" + bw(tag)] = tag_freq / word_freq
                    pos += 6 + s2t + s2f
            elif kind == "A":
                size_t = int(line[2:4])
                size_f = int(line[4:5])
                tag1 = line[6 : 6 + size_t]
                tag1_freq = float(line[7 + size_t : 7 + size_t + size_f])
                tag1_ar = bw(tag1)
                pos = 8 + size_t + size_f
                n = len(line)
                while pos < n:
                    s2t = int(line[pos : pos + 2])
                    s2f = int(line[pos + 2 : pos + 3])
                    tag2 = line[pos + 4 : pos + 4 + s2t]
                    tag2_freq = float(line[pos + 4 + s2t : pos + 5 + s2t + s2f])
                    transition[tag1_ar + ":" + bw(tag2)] = tag2_freq / tag1_freq
                    pos += 6 + s2t + s2f
    return start, emission, transition


class LanguageModel:
    """Lazy, cached access to the ``.lm`` matrices and the corpus freq maps.

    Cheap to construct — all state lives in module-level caches, so instances
    share one in-memory copy of the (large) model.
    """

    @property
    def start(self) -> dict[str, tuple[float, float]]:
        return load_lm()[0]

    @property
    def emission(self) -> dict[str, float]:
        return load_lm()[1]

    @property
    def transition(self) -> dict[str, float]:
        return load_lm()[2]

    @property
    def map_lemma(self) -> dict[str, float]:
        return load_map(MAP_LEMMA)

    @property
    def map_stem(self) -> dict[str, int]:
        return load_map(MAP_STEM)

    @property
    def map_root(self) -> dict[str, int]:
        return load_map(MAP_ROOT)
