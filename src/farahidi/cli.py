"""Command-line interface for farahidi.

Two subcommands mirror the library's two entry points:

    farahidi analyze الكتاب          # Layer 1: every morphological analysis of each word
    farahidi text "ذهب الولد"         # Layer 2: one result per token, in context

Each accepts ``-f/--format {raw,table,json,csv}`` (default ``raw``) and reads from
stdin when given no positional argument (``analyze`` splits stdin on whitespace
into words; ``text`` treats it as the text to tokenize).

``analyze`` prints one record per morphological reading; the إعراب variants
(case/mood, definiteness state, fully vowelled form) are nested under
``inflections`` in JSON and omitted from the flat formats. ``-i/--inflections``
expands them instead: one record per *(reading × ending)*, with the extra
``inflected`` / ``case`` / ``mood`` / ``state`` columns, as the original AlKhalil
output did.

Output formats:

* ``raw``   — TAB-separated, one record per line, no header (grep/cut/awk-friendly).
* ``table`` — aligned columns with a header; column widths account for Arabic
  combining diacritics, but RTL terminals may still reorder cells visually.
* ``json``  — JSON Lines. ``analyze`` nests every analysis under its word;
  ``text`` emits one token result per line.
* ``csv``   — RFC-4180 with a header row.

The flat formats (``raw``/``table``/``csv``) share one column schema; ``json``
keeps the nested structure. ``--json`` is a hidden alias for ``--format json``.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import unicodedata
from collections.abc import Iterable, Sequence
from typing import Any

from . import __version__, analyze, analyze_text
from .models import Analysis, TokenResult

# Flat-format column schemas. ``analyze`` denormalizes: the input word is repeated
# on every row; ``text`` is one row per token.
_ANALYSIS_FIELDS = (
    "diacritized",
    "lemma",
    "root",
    "stem",
    "pattern",
    "lemma_pattern",
    "pos",
    "type",
    "tense",
    "gender",
    "number",
    "person",
    "pronoun",
    "voice",
    "transitivity",
    "augmentation",
    "emphatic",
    "proclitics",
    "prefixes",
    "suffixes",
    "enclitics",
)
_INFLECTION_FIELDS = ("inflected", "case", "mood", "state")
_ANALYZE_COLUMNS = ("word", *_ANALYSIS_FIELDS, "score")
_INFLECTED_COLUMNS = ("word", *_ANALYSIS_FIELDS, *_INFLECTION_FIELDS, "score")
_TEXT_COLUMNS = ("token", "lemma", "stem", "root", "analyzed")


# ----------------------------------------------------------------- formatting
def _display_width(s: str) -> int:
    """Visible width: combining marks (Arabic harakat) render zero-width."""
    return sum(not unicodedata.combining(ch) for ch in s)


def _pad(s: str, width: int) -> str:
    return s + " " * (width - _display_width(s))


def _cell(value: Any) -> str:
    """Render one field for the flat formats."""
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, tuple | list):
        return ", ".join(a["form"] + (f" ({a['description']})" if a.get("description") else "") for a in value)
    return str(value)


def _emit_json(obj: object) -> None:
    print(json.dumps(obj, ensure_ascii=False))


def _write_raw(columns: Sequence[str], rows: Iterable[Sequence[str]]) -> None:
    for row in rows:
        print("\t".join(row))


def _write_table(columns: Sequence[str], rows: Iterable[Sequence[str]]) -> None:
    rows = list(rows)
    widths = [_display_width(c) for c in columns]
    for row in rows:
        for i, cell in enumerate(row):
            widths[i] = max(widths[i], _display_width(cell))
    sep = "  "
    print(sep.join(_pad(c, widths[i]) for i, c in enumerate(columns)))
    print(sep.join("-" * w for w in widths))
    for row in rows:
        print(sep.join(_pad(cell, widths[i]) for i, cell in enumerate(row)))


def _write_csv(columns: Sequence[str], rows: Iterable[Sequence[str]]) -> None:
    writer = csv.writer(sys.stdout, lineterminator="\n")
    writer.writerow(columns)
    writer.writerows(rows)


_FLAT_WRITERS = {"raw": _write_raw, "table": _write_table, "csv": _write_csv}


# ----------------------------------------------------------------- subcommands
def _records(a: Analysis, inflections: bool) -> list[dict[str, Any]]:
    """One dict per output record for analysis ``a``: the analysis itself, or
    (with ``inflections``) one flattened dict per inflection."""
    d = a.to_dict()
    if not inflections:
        return [d]
    del d["inflections"]
    out = []
    for infl in a.inflections:
        rec = dict(d)
        rec.update(inflected=infl.diacritized, case=infl.case, mood=infl.mood, state=infl.state, score=infl.score)
        out.append(rec)
    return out


def _token_row(r: TokenResult) -> list[str]:
    return [r.token, r.lemma, r.stem, _cell(r.root), _cell(r.analyzed)]


def _cmd_analyze(words: list[str], fmt: str, inflections: bool) -> None:
    if fmt == "json":
        for word in words:
            recs = [rec for a in analyze(word) for rec in _records(a, inflections)]
            _emit_json({"word": word, "analyses": recs})
        return
    columns = _INFLECTED_COLUMNS if inflections else _ANALYZE_COLUMNS
    rows = [
        [word, *(_cell(rec[c]) for c in columns[1:])]
        for word in words
        for a in analyze(word)
        for rec in _records(a, inflections)
    ]
    _FLAT_WRITERS[fmt](columns, rows)


def _cmd_text(text: str, fmt: str) -> None:
    results = analyze_text(text)
    if fmt == "json":
        for r in results:
            _emit_json(r.to_dict())
        return
    _FLAT_WRITERS[fmt](_TEXT_COLUMNS, [_token_row(r) for r in results])


# ---------------------------------------------------------------------- parser
def _add_format_arg(parser: argparse.ArgumentParser) -> None:
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "-f",
        "--format",
        choices=("raw", "table", "json", "csv"),
        default="raw",
        dest="format",
        help="output format (default: raw)",
    )
    group.add_argument(
        "--json",
        action="store_const",
        const="json",
        dest="format",
        help=argparse.SUPPRESS,  # back-compat alias for --format json
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="farahidi",
        description="Arabic morphological analyzer (AlKhalil Morpho Sys 2 port).",
    )
    parser.add_argument("--version", action="version", version=f"farahidi {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    p_analyze = sub.add_parser(
        "analyze",
        help="out-of-context: list every morphological analysis of each word (Layer 1)",
    )
    p_analyze.add_argument("words", nargs="*", help="words to analyze (default: read from stdin)")
    p_analyze.add_argument(
        "-i",
        "--inflections",
        action="store_true",
        help="one record per إعراب variant (case/mood + fully vowelled form) instead of one per reading",
    )
    _add_format_arg(p_analyze)

    p_text = sub.add_parser(
        "text",
        help="in-context: one disambiguated result per token (Layer 2)",
    )
    p_text.add_argument("text", nargs="*", help="text to analyze (default: read from stdin)")
    _add_format_arg(p_text)

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)

    if args.command == "analyze":
        words = args.words or sys.stdin.read().split()
        _cmd_analyze(words, args.format, args.inflections)
    elif args.command == "text":
        text = " ".join(args.text) if args.text else sys.stdin.read()
        _cmd_text(text, args.format)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
