"""Decode a ``PartOfSpeech`` record's coded fields into Arabic labels.

Each coded field (gender, number, voice, …) indexes a per-feature ``VEntity``
list (``valAR``/``valEN``). The assembled ``partofspeech`` strings match the
pipe-joined order built in ``VerbalAnalyzerImpl`` / ``NominalAnalyzerImpl``.
"""

from __future__ import annotations

from .lexicon import Lexicon

# verb feature -> PartOfSpeech field name
_VERB_FEATURES = {
    "Main": "main",
    "Type": "type",
    "Augmented": "augmented",
    "Emphasized": "emphasized",
    "NbRoot": "nbroot",
    "Person": "person",
    "Person2": "person2",
    "Transitivity": "transitivity",
    "Voice": "voice",
}

_NOUN_FEATURES = {
    "Main": "main",
    "Type": "type",
    "Definit": "definit",
    "Gender": "gender",
    "NbRoot": "nbroot",
    "Number": "number",
}


def _decode(lex: Lexicon, cat: str, pos: dict, features: dict[str, str]) -> dict[str, str]:
    out: dict[str, str] = {}
    for feature, field in features.items():
        code = pos.get(field)
        ve = lex.feature(cat, feature, int(code)) if code is not None else None
        out[feature] = ve["valAR"] if ve else ""
    return out


def decode_verb(lex: Lexicon, pos_id: int) -> dict:
    """Return decoded verb features + freq + assembled ``partofspeech`` string."""
    pos = lex.pos("Verbs", pos_id)
    d = _decode(lex, "Verbs", pos, _VERB_FEATURES)
    d["freq"] = pos["freq"]
    # Order from VerbalAnalyzerImpl: main|type|emphasized|voice|nbroot|augmented|person|person2|transitivity
    d["partofspeech"] = "|".join(
        [
            d["Main"],
            d["Type"],
            d["Emphasized"],
            d["Voice"],
            d["NbRoot"],
            d["Augmented"],
            d["Person"],
            d["Person2"],
            d["Transitivity"],
        ]
    )
    return d


def decode_noun(lex: Lexicon, pos_id: int) -> dict:
    """Return decoded noun features + freq (the ``partofspeech`` string is
    assembled by the nominal analyzer, since its last field depends on the
    computed definiteness)."""
    pos = lex.pos("Nouns", pos_id)
    d = _decode(lex, "Nouns", pos, _NOUN_FEATURES)
    d["freq"] = pos["freq"]
    return d
