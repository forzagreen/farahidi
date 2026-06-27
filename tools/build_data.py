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

# Only Layer-1 (out-of-context) tables are bundled. The `DATA.MSA.*` corpus
# frequency tables and the 14 MB `.lm` model are used solely for Layer-2
# in-context disambiguation and will be added in a later release — excluding
# them keeps the wheel lean and contains exactly what the analyzer reads.
EXCLUDE_PREFIXES = ("DATA.MSA",)

HERE = Path(__file__).resolve().parent
PKG_DATA = HERE.parent / "src" / "farahidi" / "data"
DEFAULT_SOURCE = HERE.parent.parent / "data-json" / "alkhalil"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--source",
        type=Path,
        default=DEFAULT_SOURCE,
        help=f"directory of AlKhalil *.jsonl tables (default: {DEFAULT_SOURCE})",
    )
    args = ap.parse_args()
    source: Path = args.source

    if not source.is_dir():
        print(f"error: source dir not found: {source}", file=sys.stderr)
        return 1

    files = sorted(p for p in source.glob("*.jsonl") if not p.name.startswith(EXCLUDE_PREFIXES))
    if not files:
        print(f"error: no *.jsonl files in {source}", file=sys.stderr)
        return 1

    if PKG_DATA.exists():
        shutil.rmtree(PKG_DATA)
    PKG_DATA.mkdir(parents=True)

    manifest: list[str] = []
    total_in = total_out = 0
    for src in files:
        dst = PKG_DATA / (src.name + ".gz")
        raw = src.read_bytes()
        # mtime=0 → reproducible output (same bytes across rebuilds).
        with gzip.GzipFile(filename="", fileobj=dst.open("wb"), mode="wb", mtime=0) as gz:
            gz.write(raw)
        total_in += len(raw)
        total_out += dst.stat().st_size
        digest = hashlib.sha256(raw).hexdigest()[:16]
        manifest.append(f"{src.name}\t{len(raw)}\t{digest}")

    (PKG_DATA / "MANIFEST.txt").write_text(
        "# AlKhalil Morpho Sys 2 data (Oujda NLP Team, GPL-3.0). filename\tbytes\tsha256[:16]\n"
        + "\n".join(manifest)
        + "\n",
        encoding="utf-8",
    )

    print(
        f"bundled {len(files)} tables: {total_in / 1e6:.1f} MB -> "
        f"{total_out / 1e6:.1f} MB gzip into {PKG_DATA}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
