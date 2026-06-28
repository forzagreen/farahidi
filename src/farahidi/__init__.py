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
from .disambiguate import Disambiguator
from .models import Analysis, TokenResult

__all__ = [
    "Analyzer",
    "Analysis",
    "Disambiguator",
    "TokenResult",
    "analyze",
    "analyze_text",
    "__version__",
]
__version__ = "0.3.0"


@lru_cache(maxsize=1)
def _default_analyzer() -> Analyzer:
    return Analyzer()


@lru_cache(maxsize=1)
def _default_disambiguator() -> Disambiguator:
    return Disambiguator(analyzer=_default_analyzer())


def analyze(word: str) -> list[Analysis]:
    """Return all analyses of ``word``, sorted by ``priority`` (descending).

    Uses a shared module-level :class:`Analyzer`.
    """
    return _default_analyzer().analyze(word)


def analyze_text(text: str) -> list[TokenResult]:
    """In-context analysis: one chosen lemma/stem/root per word token across the
    sentence(s) in ``text``. Uses a shared module-level :class:`Disambiguator`.
    """
    return _default_disambiguator().analyze_text(text)
