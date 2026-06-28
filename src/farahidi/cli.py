"""Command-line interface for farahidi.

Two subcommands mirror the library's two entry points:

    farahidi analyze الكتاب          # Layer 1: every analysis of each word
    farahidi text "ذهب الولد"         # Layer 2: one result per token, in context

Each accepts ``-f/--format {raw,table,json,csv}`` (default ``raw``) and reads from
stdin when given no positional argument (``analyze`` splits stdin on whitespace
into words; ``text`` treats it as the text to tokenize).

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

from . import __version__, analyze, analyze_text
from .models import Analysis, TokenResult

# Flat-format column schemas. ``analyze`` denormalizes: the input word is repeated
# on every analysis row; ``text`` is one row per token.
_ANALYSIS_FIELDS = (
    "voweled_word",
    "proclitic",
    "stem",
    "part_of_speech",
    "diac_pattern_stem",
    "pattern_stem",
    "lemma",
    "pattern_lemma",
    "root",
    "case_or_mood",
    "enclitic",
    "priority",
)
_ANALYZE_COLUMNS = ("word", *_ANALYSIS_FIELDS)
_TEXT_COLUMNS = ("token", "lemma", "stem", "root", "analyzed")


# ----------------------------------------------------------------- formatting
def _display_width(s: str) -> int:
    """Visible width: combining marks (Arabic harakat) render zero-width."""
    return sum(not unicodedata.combining(ch) for ch in s)


def _pad(s: str, width: int) -> str:
    return s + " " * (width - _display_width(s))


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
def _analysis_row(word: str, a: Analysis) -> list[str]:
    return [word, *(getattr(a, f) for f in _ANALYSIS_FIELDS)]


def _token_row(r: TokenResult) -> list[str]:
    return [r.token, r.lemma, r.stem, r.root, "true" if r.analyzed else "false"]


def _cmd_analyze(words: list[str], fmt: str) -> None:
    if fmt == "json":
        for word in words:
            _emit_json({"word": word, "analyses": [a.to_dict() for a in analyze(word)]})
        return
    rows = [_analysis_row(word, a) for word in words for a in analyze(word)]
    _FLAT_WRITERS[fmt](_ANALYZE_COLUMNS, rows)


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
        help="out-of-context: list every analysis of each word (Layer 1)",
    )
    p_analyze.add_argument("words", nargs="*", help="words to analyze (default: read from stdin)")
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
        _cmd_analyze(words, args.format)
    elif args.command == "text":
        text = " ".join(args.text) if args.text else sys.stdin.read()
        _cmd_text(text, args.format)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
