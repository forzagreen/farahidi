"""Public output type: one morphological analysis of a word."""

from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True, slots=True)
class Analysis:
    """A single analysis, mirroring AlKhalil's ``Result`` (12 fields).

    Strings are in Arabic script. ``"-"`` means "not applicable" (e.g. a tool
    word has no root); ``"#"`` marks an absent clitic, as in the reference.
    ``priority`` is the out-of-context ranking weight (higher = more frequent);
    use :meth:`farahidi.analyze` which returns analyses already sorted by it.
    """

    voweled_word: str
    proclitic: str
    stem: str
    part_of_speech: str
    diac_pattern_stem: str
    pattern_stem: str
    lemma: str
    pattern_lemma: str
    root: str
    case_or_mood: str
    enclitic: str
    priority: str

    def to_dict(self) -> dict[str, str]:
        return asdict(self)
