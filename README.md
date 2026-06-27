# farahidi

**Arabic morphological analyzer for Python** — a pure-Python re-implementation of
[AlKhalil Morpho Sys 2](https://alkhalil.oujda-nlp-team.net/) (Oujda NLP Team).

Given an Arabic word, `farahidi` returns every valid morphological analysis —
**root, lemma, stem, pattern (wazn), part of speech with full features, case/mood,
and segmented proclitics/enclitics** — ranked by corpus frequency.

- **Pure Python, zero dependencies.** Works on CPython 3.11 – 3.14.
- **Offline.** The full lexicon (~404k records) ships compressed inside the wheel
  (~7 MB); nothing is downloaded at runtime.
- **Faithful.** Output is validated against the original Java `AlKhalil2Analyzer`.

> Named after **al-Khalīl ibn Aḥmad al-Farāhīdī** (الخليل بن أحمد الفراهيدي), the
> 8th-century founder of Arabic lexicography and prosody.

## Install

```bash
pip install farahidi
# or
uv add farahidi
```

## Usage

```python
import farahidi

for a in farahidi.analyze("لِأَنَّهُمْ"):
    print(a.voweled_word, a.lemma, a.root, a.part_of_speech)
```

`analyze()` returns a list of `Analysis` objects, sorted by `priority`
(most frequent analysis first). Each `Analysis` has these fields (Arabic script;
`"-"` = not applicable, `"#"` = absent clitic):

| field | meaning |
|---|---|
| `voweled_word` | fully diacritized surface form |
| `proclitic` / `enclitic` | segmented clitics with their descriptions |
| `stem` | the bare stem |
| `lemma` | dictionary form |
| `root` | the (3- or 4-letter) root |
| `pattern_stem` / `pattern_lemma` | canonical patterns (wazn) |
| `diac_pattern_stem` | diacritic pattern of the stem |
| `part_of_speech` | pipe-joined POS + morpho-syntactic features |
| `case_or_mood` | إعراب (case for nouns, mood for verbs) |
| `priority` | out-of-context ranking weight (higher = more frequent) |

For repeated analysis, build one reusable analyzer (the lexicon loads lazily and
is shared):

```python
from farahidi import Analyzer

az = Analyzer()
results = az.analyze("مدرسة")
```

## Scope

This release implements **Layer 1**: out-of-context analysis of a single word,
returning all candidates ranked by frequency. In-context disambiguation
(Layer 2: an HMM/Viterbi decode over a sentence) is planned for a later release.

## Data & license

`farahidi` is licensed under the **GPL-3.0-or-later**, because it bundles and
derives from AlKhalil Morpho Sys 2's GPL-3.0 linguistic data. Simply *using* the
library (e.g. `pip install` and calling `analyze`) places no obligations on your
own code or its outputs. See [`NOTICE`](NOTICE) for attribution to the Oujda NLP
Team and [`LICENSE`](LICENSE) for the full terms.

## Development

```bash
uv sync
uv run pytest
uv run ruff check
```

The bundled data is regenerated from the parent `morph-analyzer` export with
`python tools/build_data.py`. Golden test fixtures are produced from the Java
reference with `tools/AlkhalilGolden.java` (see `tools/gen_golden.py`).
