#!/usr/bin/env python3
"""Regenerate the golden test fixtures from the Java AlKhalil reference.

Two modes:

* ``words`` (default) — compiles ``tools/AlkhalilGolden.java`` and runs it over
  ``tools/wordlist.txt``, writing ``tests/fixtures/golden.jsonl`` (Layer-1: every
  analysis's 12 fields per word).
* ``sentences`` — compiles ``tools/AlkhalilSentenceGolden.java`` and runs it over
  ``tools/sentences.txt``, writing ``tests/fixtures/sentences.jsonl`` (Layer-2: the
  chosen lemma/stem/root per token, from ``ADATAnalyzer``).

The committed fixtures are what the test suite checks against, so this tool is
only needed when changing the inputs or upgrading the upstream data. It requires
a JDK and the ``AlkhalilMorphSys2/`` sources:

    python tools/gen_golden.py [--mode words|sentences] [--alkhalil ../AlkhalilMorphSys2]
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
DEFAULT_ALKHALIL = ROOT.parent / "AlkhalilMorphSys2"

MODES = {
    # mode: (harness .java, default input, default output)
    "words": ("AlkhalilGolden.java", "wordlist.txt", "golden.jsonl"),
    "sentences": ("AlkhalilSentenceGolden.java", "sentences.txt", "sentences.jsonl"),
}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--mode", choices=sorted(MODES), default="words")
    ap.add_argument("--alkhalil", type=Path, default=DEFAULT_ALKHALIL)
    ap.add_argument("--input", type=Path, default=None)
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args()

    harness, default_in, default_out = MODES[args.mode]
    input_path = args.input or HERE / default_in
    out_path = args.out or ROOT / "tests" / "fixtures" / default_out

    src = args.alkhalil / "src"
    if not src.is_dir():
        print(f"error: AlKhalil source not found at {src}", file=sys.stderr)
        print("Pass --alkhalil pointing at the AlkhalilMorphSys2 checkout.", file=sys.stderr)
        return 1

    build = HERE / "build"
    build.mkdir(exist_ok=True)
    print(f"compiling Java reference + {harness} ...")
    # -sourcepath lets javac pull in the harness's transitive AlKhalil deps.
    subprocess.run(
        ["javac", "-encoding", "UTF-8", "-d", str(build), "-cp", str(src),
         "-sourcepath", str(src), str(HERE / harness)],
        check=True,
    )

    main_class = Path(harness).stem
    print(f"running {main_class} over {input_path} ...")
    with input_path.open("rb") as fin, out_path.open("wb") as fout:
        subprocess.run(
            ["java", "-Dfile.encoding=UTF-8", "-cp", f"{build}:{src}", main_class],
            stdin=fin, stdout=fout, check=True,
        )
    print(f"wrote {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
