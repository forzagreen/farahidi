"""Public result types.

Layer 1 (:func:`farahidi.analyze`) returns :class:`Analysis` objects — one per
*morphological* reading of the word. Everything that depends on the word's
syntactic role in a sentence (the إعراب: case for nouns, mood for verbs, and the
definiteness *state*) is kept apart in :class:`Inflection` objects nested under
``Analysis.inflections``, so a word like ``عندليب`` yields a single analysis with
five inflections instead of five near-identical analyses.

Layer 2 (:func:`farahidi.analyze_text`) returns one :class:`TokenResult` per
token.

Conventions: all linguistic labels are Arabic strings exactly as found in the
AlKhalil lexicon; ``None`` means "not applicable" (a particle has no root, a
noun has no mood …); affix lists are empty when the word has none.
"""

from __future__ import annotations

from dataclasses import dataclass, fields
from typing import Any


def _compact_repr(obj: Any) -> str:
    """``repr`` that omits ``None`` fields and empty tuples."""
    parts = []
    for f in fields(obj):
        value = getattr(obj, f.name)
        if value is None or value == ():
            continue
        parts.append(f"{f.name}={value!r}")
    return f"{type(obj).__name__}({', '.join(parts)})"


def _plain(value: Any) -> Any:
    """Recursively convert dataclasses to dicts and tuples to lists."""
    if hasattr(value, "__dataclass_fields__"):
        return {f.name: _plain(getattr(value, f.name)) for f in fields(value)}
    if isinstance(value, tuple | list):
        return [_plain(v) for v in value]
    return value


@dataclass(frozen=True, slots=True, repr=False)
class Affix:
    """A segmented piece of the word that is not part of the stem.

    ``form`` is the diacritized surface string; ``description`` is the lexicon's
    label for its function (e.g. ``حرف الجر``, ``ضمير الغائبين``). A clitic that
    bundles several functions keeps the lexicon's compound label
    (``حرف العطف+حرف الجر``). ``description`` is ``None`` when the lexicon has
    no label (only for the handful of fixed expressions built on ``الله``).
    """

    form: str
    description: str | None = None

    def __repr__(self) -> str:
        return _compact_repr(self)

    def to_dict(self) -> dict[str, Any]:
        return _plain(self)


@dataclass(frozen=True, slots=True, repr=False)
class Inflection:
    """One syntactic realization (إعراب) of an :class:`Analysis`.

    ``diacritized`` is the fully vowelled surface form *including* the case/mood
    ending. ``case`` (nouns: مرفوع / منصوب / مجرور) or ``mood`` (verbs: مرفوع /
    منصوب / مجزوم) names that ending; both are ``None`` for indeclinable words
    (مبني: particles, past and imperative verbs, …), which then have exactly one
    inflection. ``state`` is the noun's definiteness state (نكرة / معرف بأل /
    مضاف …) that AlKhalil infers together with the ending. ``score`` is this
    realization's own out-of-context weight.
    """

    diacritized: str
    case: str | None
    mood: str | None
    state: str | None
    score: float

    def __repr__(self) -> str:
        return _compact_repr(self)

    def to_dict(self) -> dict[str, Any]:
        return _plain(self)


@dataclass(frozen=True, slots=True, repr=False)
class Analysis:
    """One morphological analysis (تحليل صرفي) of a word.

    Fields
    ------
    diacritized
        The word with its diacritics, *without* the inflectional ending on the
        last letter (``عَنْدَلِيب``, ``بِالْمَدْرَسَة``, ``يَكْتُب``). The fully
        vowelled variants live in ``inflections``.
    lemma, root, stem
        Dictionary form, the 3- or 4-letter root (``None`` for particles and most
        proper nouns) and the clitic-free stem.
    pattern, lemma_pattern
        The canonical patterns (وزن) of the stem and of the lemma; ``None`` for
        words that have no pattern (particles, proper nouns).
    pos, type
        Main part of speech (``اسم`` / ``فعل`` / ``حرف``) and its sub-type: the
        derivational type of a noun (``اسم فاعل``, ``مصدر أصلي`` …), the function
        of a particle (``جر``, ``عطف`` …), ``اسم علم`` for proper nouns.
    tense, voice, person, pronoun, transitivity, augmentation, emphatic
        Verb features: ماض / مضارع / أمر, معلوم / مجهول, متكلم / مخاطب / غائب, the
        subject pronoun (``هو``, ``أنتَ``, ``نحن`` …), لازم / متعد, مجرد / مزيد and
        whether a نون التوكيد is attached. ``tense`` and ``person`` are also set
        for the few tool words that carry them.
    gender, number
        Noun features: مذكر / مؤنث and مفرد / مثنى / جمع.
    proclitics, prefixes, suffixes, enclitics
        Segmentation around the stem, outermost first: clitics (``وَ``, ``بِ``,
        ``ال`` … / attached pronouns) and inflectional affixes (the مضارع prefix,
        subject suffixes, ``ة``, ``ات``, ``ان`` …).
    score
        Out-of-context ranking weight, higher = more frequent (the best of the
        inflections' scores). :func:`farahidi.analyze` sorts by it.
    inflections
        The syntactic realizations of this reading, best first.
    """

    diacritized: str
    lemma: str
    root: str | None
    stem: str
    pattern: str | None
    lemma_pattern: str | None
    pos: str
    type: str | None
    tense: str | None
    gender: str | None
    number: str | None
    person: str | None
    pronoun: str | None
    voice: str | None
    transitivity: str | None
    augmentation: str | None
    emphatic: bool | None
    proclitics: tuple[Affix, ...]
    prefixes: tuple[Affix, ...]
    suffixes: tuple[Affix, ...]
    enclitics: tuple[Affix, ...]
    score: float
    inflections: tuple[Inflection, ...]

    def __repr__(self) -> str:
        return _compact_repr(self)

    def to_dict(self) -> dict[str, Any]:
        """Plain nested ``dict``/``list`` structure (JSON-serializable)."""
        return _plain(self)


@dataclass(frozen=True, slots=True)
class TokenResult:
    """One token's in-context (Layer-2) disambiguation result.

    Mirrors AlKhalil's ``ADATAnalyzer`` outputs: ``lemma`` is the single analysis
    chosen by the HMM, ``stem`` / ``root`` are then the highest-corpus-frequency
    stem/root among the analyses sharing that lemma (lemmatizer / light stemmer /
    heavy stemmer respectively). ``root`` is ``None`` when the chosen reading has
    no root (particles). ``analyzed`` is ``False`` for tokens the analyzer could
    not analyze, in which case ``lemma`` and ``stem`` fall back to ``token`` and
    ``root`` is ``None``. All strings are Arabic script.
    """

    token: str
    lemma: str
    stem: str
    root: str | None
    analyzed: bool

    def to_dict(self) -> dict[str, Any]:
        return _plain(self)
