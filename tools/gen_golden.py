#!/usr/bin/env python3
"""Regenerate the golden test fixture from the Java AlKhalil reference.

Compiles ``tools/AlkhalilGolden.java`` against the original AlKhalil Morpho Sys 2
source (in the parent ``morph-analyzer`` repo) and runs it over
``tools/wordlist.txt``, writing ``tests/fixtures/golden.jsonl`` (one JSON object
per word with every analysis's 12 fields).

The committed fixture is what the test suite checks against, so this tool is only
needed when changing the wordlist or upgrading the upstream data. It requires a
JDK and the ``AlkhalilMorphSys2/`` sources:

    python tools/gen_golden.py [--alkhalil ../AlkhalilMorphSys2]
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
DEFAULT_ALKHALIL = ROOT.parent / "AlkhalilMorphSys2"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--alkhalil", type=Path, default=DEFAULT_ALKHALIL)
    ap.add_argument("--wordlist", type=Path, default=HERE / "wordlist.txt")
    ap.add_argument("--out", type=Path, default=ROOT / "tests" / "fixtures" / "golden.jsonl")
    args = ap.parse_args()

    src = args.alkhalil / "src"
    if not src.is_dir():
        print(f"error: AlKhalil source not found at {src}", file=sys.stderr)
        print("Pass --alkhalil pointing at the AlkhalilMorphSys2 checkout.", file=sys.stderr)
        return 1

    build = HERE / "build"
    build.mkdir(exist_ok=True)
    print("compiling Java reference + harness ...")
    subprocess.run(
        ["javac", "-encoding", "UTF-8", "-d", str(build), "-cp", str(src),
         str(HERE / "AlkhalilGolden.java"), str(src / "net/oujda_nlp_team/AlKhalil2Analyzer.java")],
        check=True,
    )

    print(f"running harness over {args.wordlist} ...")
    with args.wordlist.open("rb") as fin, args.out.open("wb") as fout:
        subprocess.run(
            ["java", "-Dfile.encoding=UTF-8", "-cp", f"{build}:{src}", "AlkhalilGolden"],
            stdin=fin, stdout=fout, check=True,
        )
    print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
