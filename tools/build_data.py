#!/usr/bin/env python3
"""Bundle AlKhalil data into the farahidi package.

Reads the JSONL tables exported by the parent `morph-analyzer` repo
(``data-json/alkhalil/*.jsonl``) and writes gzip-compressed copies into
``src/farahidi/data/``. The full set gzips to roughly 7 MB, so it ships
directly inside the wheel — the library needs no network at runtime.

This is a maintainer tool, not part of the installed package. Run it once
when the upstream data changes:

    python tools/build_data.py [--source ../data-json/alkhalil]
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import shutil
import sys
from pathlib import Path

# Most `DATA.MSA.*` tables stay excluded, but Layer-2 in-context disambiguation
# needs three of them (the lemma backoff weights + stem/root corpus counts) plus
# the plain-text `.lm` model. Everything else under `DATA.MSA.*` is skipped
# (e.g. DATA.MSA.SHA.LEMMA, used only by the unused ADATAnalyzer1).
EXCLUDE_PREFIXES = ("DATA.MSA",)
LAYER2_MAPS = {
    "DATA.MSA-LEMMA.ALL-train.map.jsonl",  # mapLemma — backoff weights (float)
    "DATA.MSA.SHA.STEM.map.jsonl",  # mapStem — stem corpus counts (int)
    "DATA.MSA.SHA.ROOT.map.jsonl",  # mapRoot — root corpus counts (int)
}
# The HMM language model: plain-text, length-prefixed, Buckwalter (~14 MB).
LM_NAME = "DATA.MSA.ALL.TRAIN.141809.lm"
LM_RELPATH = Path("src/net/oujda_nlp_team/resources") / LM_NAME

HERE = Path(__file__).resolve().parent
PKG_DATA = HERE.parent / "src" / "farahidi" / "data"
DEFAULT_SOURCE = HERE.parent.parent / "data-json" / "alkhalil"
DEFAULT_ALKHALIL = HERE.parent.parent / "AlkhalilMorphSys2"


def _gzip_to(raw: bytes, dst: Path) -> int:
    # mtime=0 → reproducible output (same bytes across rebuilds).
    with gzip.GzipFile(filename="", fileobj=dst.open("wb"), mode="wb", mtime=0) as gz:
        gz.write(raw)
    return dst.stat().st_size


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--source",
        type=Path,
        default=DEFAULT_SOURCE,
        help=f"directory of AlKhalil *.jsonl tables (default: {DEFAULT_SOURCE})",
    )
    ap.add_argument(
        "--alkhalil",
        type=Path,
        default=DEFAULT_ALKHALIL,
        help=f"AlkhalilMorphSys2 checkout (for the .lm; default: {DEFAULT_ALKHALIL})",
    )
    args = ap.parse_args()
    source: Path = args.source

    if not source.is_dir():
        print(f"error: source dir not found: {source}", file=sys.stderr)
        return 1

    lm_src = args.alkhalil / LM_RELPATH
    if not lm_src.is_file():
        print(f"error: .lm model not found: {lm_src}", file=sys.stderr)
        return 1

    files = sorted(
        p
        for p in source.glob("*.jsonl")
        if not p.name.startswith(EXCLUDE_PREFIXES) or p.name in LAYER2_MAPS
    )
    if not files:
        print(f"error: no *.jsonl files in {source}", file=sys.stderr)
        return 1

    if PKG_DATA.exists():
        shutil.rmtree(PKG_DATA)
    PKG_DATA.mkdir(parents=True)

    manifest: list[str] = []
    total_in = total_out = 0
    for src in [*files, lm_src]:
        dst = PKG_DATA / (src.name + ".gz")
        raw = src.read_bytes()
        total_out += _gzip_to(raw, dst)
        total_in += len(raw)
        digest = hashlib.sha256(raw).hexdigest()[:16]
        manifest.append(f"{src.name}\t{len(raw)}\t{digest}")

    (PKG_DATA / "MANIFEST.txt").write_text(
        "# AlKhalil Morpho Sys 2 data (Oujda NLP Team, GPL-3.0). filename\tbytes\tsha256[:16]\n"
        + "\n".join(manifest)
        + "\n",
        encoding="utf-8",
    )

    print(
        f"bundled {len(files) + 1} files (incl. the .lm): {total_in / 1e6:.1f} MB -> "
        f"{total_out / 1e6:.1f} MB gzip into {PKG_DATA}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
