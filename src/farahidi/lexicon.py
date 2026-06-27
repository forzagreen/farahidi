"""Lazy, cached access to the bundled AlKhalil data tables.

The data ships as gzip-compressed JSONL inside ``farahidi/data/``. Each table is
loaded at most once, on first use, and cached. ``*.map.jsonl`` files become a
``dict`` keyed by the record ``key``; ``*.list.jsonl`` files become a ``list`` of
records. See ``DATA-FORMATS.md`` in the parent repo for the field schema.

The :class:`Lexicon` accessors mirror the Java ``DerivedFactory`` /
``CliticFactory`` lookups so the analyzer can follow the same joins.
"""

from __future__ import annotations

import gzip
import json
from functools import cache
from importlib.resources import files
from typing import Any

# Logical name -> bundled filename (from AlKhalil2.properties). Only the tables
# used by Layer-1 analysis are listed.
TABLES: dict[str, str] = {
    # clitics
    "proclitics": "DATA.Clitics.Proclitics.map",
    "enclitics": "DATA.Clitics.Enclitics.map",
    # exceptional
    "exceptional": "DATA.Exceptional.map",
    # proper nouns
    "propernoun_unvoweled": "DATA.NonDerived.Propernoun.Unvoweled.map",
    "propernoun_voweled": "DATA.NonDerived.Propernoun.Voweled.list",
    "propernoun_pos": "DATA.NonDerived.Propernoun.PartOfSpeech.list",
    "propernoun_casemood": "DATA.NonDerived.Propernoun.CaseOrMood.list",
    # toolwords
    "toolwords_unvoweled": "DATA.NonDerived.Toolwords.Unvoweled.map",
    "toolwords_voweled": "DATA.NonDerived.Toolwords.Voweled.list",
    "toolwords_pos": "DATA.NonDerived.Toolwords.PartOfSpeech.list",
    # roots
    "root_freq": "DATA.Root.map",
}

# Per-category (verbs/nouns) tables, formatted with the category name.
DERIVED_TABLES: dict[str, str] = {
    "unvoweled_stem": "DATA.Derived.{cat}.Patterns.Stems.Unvoweled.map",
    "voweled_diac_stem": "DATA.Derived.{cat}.Patterns.Stems.Voweled.Diac.map",
    "voweled_canonic_stem": "DATA.Derived.{cat}.Patterns.Stems.Voweled.Canonic.map",
    "voweled_diac_lemma": "DATA.Derived.{cat}.Patterns.Lemmas.Voweled.Diac.map",
    "voweled_canonic_lemma": "DATA.Derived.{cat}.Patterns.Lemmas.Voweled.Canonic.map",
    "roots_tri": "DATA.Derived.{cat}.Roots.Trilateral.map",
    "roots_quad": "DATA.Derived.{cat}.Roots.Quadriliteral.map",
    "roots_id_tri": "DATA.Derived.{cat}.Roots.id.Trilateral.map",
    "roots_id_quad": "DATA.Derived.{cat}.Roots.id.Quadriliteral.map",
    "formulas": "DATA.Derived.{cat}.Formulas.map",
    "pos": "DATA.Derived.{cat}.PartOfSpeech.list",
    "casemood": "DATA.Derived.{cat}.CaseOrMood.list",
}

# Per-feature VEntity lists used to decode PartOfSpeech codes.
FEATURE_TABLES: dict[str, str] = {
    "Main": "DATA.Derived.{cat}.PartOfSpeech.Main.list",
    "Type": "DATA.Derived.{cat}.PartOfSpeech.Type.list",
    "NbRoot": "DATA.Derived.{cat}.PartOfSpeech.NbRoot.list",
    # verbs
    "Augmented": "DATA.Derived.Verbs.PartOfSpeech.Augmented.list",
    "Emphasized": "DATA.Derived.Verbs.PartOfSpeech.Emphasized.list",
    "Person": "DATA.Derived.Verbs.PartOfSpeech.Person.list",
    "Person2": "DATA.Derived.Verbs.PartOfSpeech.Person2.list",
    "Transitivity": "DATA.Derived.Verbs.PartOfSpeech.Transitivity.list",
    "Voice": "DATA.Derived.Verbs.PartOfSpeech.Voice.list",
    # nouns
    "Definit": "DATA.Derived.Nouns.PartOfSpeech.Definit.list",
    "Gender": "DATA.Derived.Nouns.PartOfSpeech.Gender.list",
    "Number": "DATA.Derived.Nouns.PartOfSpeech.Number.list",
}


def _data_dir():
    return files("farahidi") / "data"


@cache
def load_map(filename: str) -> dict[Any, Any]:
    """Load a ``*.map`` table as ``{key: value}`` (cached)."""
    path = _data_dir() / (filename + ".jsonl.gz")
    out: dict[Any, Any] = {}
    with gzip.open(path.open("rb"), "rt", encoding="utf-8") as fh:
        for line in fh:
            if not line.strip():
                continue
            rec = json.loads(line)
            out[rec["key"]] = rec["value"]
    return out


@cache
def load_list(filename: str) -> list[Any]:
    """Load a ``*.list`` table as a list of records (cached)."""
    path = _data_dir() / (filename + ".jsonl.gz")
    out: list[Any] = []
    with gzip.open(path.open("rb"), "rt", encoding="utf-8") as fh:
        for line in fh:
            if not line.strip():
                continue
            out.append(json.loads(line))
    return out


class Lexicon:
    """Typed accessors over the bundled tables, mirroring the Java factories.

    Stateless and cheap to construct — all real work is the module-level
    ``lru_cache``d loaders, so multiple instances share one in-memory copy.
    """

    # --- generic map/list resolution -------------------------------------
    def map(self, logical: str) -> dict[Any, Any]:
        return load_map(TABLES[logical])

    def list(self, logical: str) -> list[Any]:
        return load_list(TABLES[logical])

    def derived_map(self, cat: str, logical: str) -> dict[Any, Any]:
        return load_map(DERIVED_TABLES[logical].format(cat=cat))

    def derived_list(self, cat: str, logical: str) -> list[Any]:
        return load_list(DERIVED_TABLES[logical].format(cat=cat))

    # --- clitics ----------------------------------------------------------
    def proclitics(self, surface: str) -> list[dict]:
        return self.map("proclitics").get(surface, [])

    def enclitics(self, surface: str) -> list[dict]:
        return self.map("enclitics").get(surface, [])

    # --- derived: patterns / roots / formulas -----------------------------
    def unvoweled_stems(self, cat: str, length: int) -> list[dict]:
        return self.derived_map(cat, "unvoweled_stem").get(length, [])

    def voweled_diac_stem(self, cat: str, length: int, index: int) -> dict | None:
        lst = self.derived_map(cat, "voweled_diac_stem").get(length)
        return lst[index - 1] if lst and 0 < index <= len(lst) else None

    def voweled_canonic_stem(self, cat: str, length: int, index: int) -> dict | None:
        lst = self.derived_map(cat, "voweled_canonic_stem").get(length)
        return lst[index - 1] if lst and 0 < index <= len(lst) else None

    def voweled_diac_lemma(self, cat: str, length: int, index: int) -> dict | None:
        lst = self.derived_map(cat, "voweled_diac_lemma").get(length)
        return lst[index - 1] if lst and 0 < index <= len(lst) else None

    def voweled_canonic_lemma(self, cat: str, length: int, index: int) -> dict | None:
        lst = self.derived_map(cat, "voweled_canonic_lemma").get(length)
        return lst[index - 1] if lst and 0 < index <= len(lst) else None

    def formulas(self, cat: str, length: int) -> list[dict]:
        return self.derived_map(cat, "formulas").get(length, [])

    def formula(self, cat: str, length: int, formula_id: int) -> dict | None:
        lst = self.formulas(cat, length)
        return lst[formula_id - 1] if 0 < formula_id <= len(lst) else None

    def contains_root(self, cat: str, root: str) -> bool:
        key = "roots_id_tri" if len(root) == 3 else "roots_id_quad"
        return root in self.derived_map(cat, key)

    def root_entity(self, cat: str, root: str) -> dict | None:
        """The Root record (with len1..len12 formula-id slots) for ``root``."""
        if len(root) == 3:
            idx_map = self.derived_map(cat, "roots_id_tri")
            char_map = self.derived_map(cat, "roots_tri")
        else:
            idx_map = self.derived_map(cat, "roots_id_quad")
            char_map = self.derived_map(cat, "roots_quad")
        if root not in idx_map:
            return None
        bucket = char_map.get(root[0])
        if bucket is None:
            return None
        idx = idx_map[root]
        return bucket[idx] if 0 <= idx < len(bucket) else None

    # --- part of speech & features ---------------------------------------
    def pos(self, cat: str, pos_id: int) -> dict | None:
        lst = self.derived_list(cat, "pos")
        return lst[pos_id - 1] if 0 < pos_id <= len(lst) else None

    def casemood(self, cat: str, casemood_id: int) -> dict | None:
        lst = self.derived_list(cat, "casemood")
        return lst[casemood_id - 1] if 0 < casemood_id <= len(lst) else None

    def feature(self, cat: str, feature: str, index: int) -> dict | None:
        lst = load_list(FEATURE_TABLES[feature].format(cat=cat))
        return lst[index - 1] if 0 < index <= len(lst) else None
