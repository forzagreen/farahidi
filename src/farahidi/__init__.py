"""farahidi — Arabic morphological analyzer (a pure-Python port of AlKhalil Morpho Sys 2).

Quick start::

    import farahidi

    for a in farahidi.analyze("بالمدرسة"):
        print(a.diacritized, a.lemma, a.root, a.pos, a.type)

:func:`analyze` returns the word's *morphological* readings as
:class:`Analysis` objects, best ``score`` first. The syntactic case/mood endings
(الإعراب) of each reading are nested under ``Analysis.inflections`` rather than
multiplying the results. For repeated use, build an :class:`Analyzer` once and
reuse it — the bundled lexicon loads lazily and is shared across calls.
"""

from __future__ import annotations

from functools import lru_cache

from .analyzer import Analyzer
from .disambiguate import Disambiguator, tokenize
from .models import Affix, Analysis, Inflection, TokenResult

__all__ = [
    "Affix",
    "Analyzer",
    "Analysis",
    "Disambiguator",
    "Inflection",
    "TokenResult",
    "analyze",
    "analyze_text",
    "tokenize",
    "__version__",
]
__version__ = "0.4.0"


@lru_cache(maxsize=1)
def _default_analyzer() -> Analyzer:
    return Analyzer()


@lru_cache(maxsize=1)
def _default_disambiguator() -> Disambiguator:
    return Disambiguator(analyzer=_default_analyzer())


def analyze(word: str) -> list[Analysis]:
    """Return all morphological analyses of ``word``, sorted by ``score``
    (descending). Uses a shared module-level :class:`Analyzer`.
    """
    return _default_analyzer().analyze(word)


def analyze_text(text: str) -> list[TokenResult]:
    """In-context analysis: one chosen lemma/stem/root per word token across the
    sentence(s) in ``text``. Uses a shared module-level :class:`Disambiguator`.
    """
    return _default_disambiguator().analyze_text(text)
