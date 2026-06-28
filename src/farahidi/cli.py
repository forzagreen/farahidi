"""Command-line interface for farahidi.

Two subcommands mirror the library's two entry points:

    farahidi analyze الكتاب          # Layer 1: every analysis of each word
    farahidi text "ذهب الولد"         # Layer 2: one result per token, in context

Both print a human-readable listing by default, accept ``--json`` for JSON Lines
output, and read from stdin when no positional argument is given (``analyze``
splits stdin on whitespace into words; ``text`` treats it as the text to tokenize).
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence

from . import __version__, analyze, analyze_text


def _read_stdin_words() -> list[str]:
    return sys.stdin.read().split()


def _emit(obj: object) -> None:
    print(json.dumps(obj, ensure_ascii=False))


def _cmd_analyze(words: list[str], as_json: bool) -> None:
    for word in words:
        analyses = analyze(word)
        if as_json:
            _emit({"word": word, "analyses": [a.to_dict() for a in analyses]})
            continue
        if not analyses:
            print(f"{word}  (no analyses)")
            continue
        print(f"{word}  ({len(analyses)} analyses)")
        for i, a in enumerate(analyses, 1):
            print(
                f"  {i:>2}. {a.voweled_word}"
                f"  lemma={a.lemma}  root={a.root}  wazn={a.pattern_stem}"
                f"  pos={a.part_of_speech}  case={a.case_or_mood}"
                f"  pro={a.proclitic}  enc={a.enclitic}  prio={a.priority}"
            )


def _cmd_text(text: str, as_json: bool) -> None:
    for r in analyze_text(text):
        if as_json:
            _emit(r.to_dict())
        else:
            print(f"{r.token}\t{r.lemma}\t{r.stem}\t{r.root}")


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
    p_analyze.add_argument("--json", action="store_true", help="emit JSON Lines")

    p_text = sub.add_parser(
        "text",
        help="in-context: one disambiguated result per token (Layer 2)",
    )
    p_text.add_argument("text", nargs="*", help="text to analyze (default: read from stdin)")
    p_text.add_argument("--json", action="store_true", help="emit JSON Lines")

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)

    if args.command == "analyze":
        words = args.words or _read_stdin_words()
        _cmd_analyze(words, args.json)
    elif args.command == "text":
        text = " ".join(args.text) if args.text else sys.stdin.read()
        _cmd_text(text, args.json)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
