"""farahidi — Arabic morphological analyzer (a pure-Python port of AlKhalil Morpho Sys 2).

Quick start::

    import farahidi

    for a in farahidi.analyze("لأنهم"):
        print(a.voweled_word, a.lemma, a.root, a.part_of_speech)

:func:`analyze` returns a list of :class:`Analysis` candidates sorted by
``priority`` (most frequent first). For repeated use, build an :class:`Analyzer`
once and reuse it — the bundled lexicon loads lazily and is shared across calls.
"""

from __future__ import annotations

from functools import lru_cache

from .analyzer import Analyzer
from .models import Analysis

__all__ = ["Analyzer", "Analysis", "analyze", "__version__"]
__version__ = "0.1.0"


@lru_cache(maxsize=1)
def _default_analyzer() -> Analyzer:
    return Analyzer()


def analyze(word: str) -> list[Analysis]:
    """Return all analyses of ``word``, sorted by ``priority`` (descending).

    Uses a shared module-level :class:`Analyzer`.
    """
    return _default_analyzer().analyze(word)
