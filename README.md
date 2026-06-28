# farahidi

**Arabic morphological analyzer for Python** — a pure-Python re-implementation of
[AlKhalil Morpho Sys 2](https://alkhalil.oujda-nlp-team.net/) (Oujda NLP Team).

Given an Arabic word, `farahidi` returns every valid morphological analysis —
**root, lemma, stem, pattern (wazn), part of speech with full features, case/mood,
and segmented proclitics/enclitics** — ranked by corpus frequency.

- **Pure Python, zero dependencies.** Works on CPython 3.11 – 3.14.
- **Offline.** The full lexicon plus the in-context language model ship compressed
  inside the wheel (~11 MB); nothing is downloaded at runtime.
- **Faithful.** Output is validated against the original Java `AlKhalil2Analyzer`
  (single-word) and `ADATAnalyzer` (in-context).

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

### In-context disambiguation

`analyze_text()` picks the single best analysis per token across a sentence,
returning one `TokenResult` per word with the chosen `lemma`, `stem`, and `root`:

```python
import farahidi

for r in farahidi.analyze_text("ذهب الولد إلى المدرسة"):
    print(r.token, r.lemma, r.stem, r.root)
# ذهب ذَهَبَ ذَهَب ذهب
# الولد وَلَد وَلَد ولد
# إلى إِلَى إِلَى -
# المدرسة مَدْرَسَة مَدْرَسَة درس
```

A reusable `Disambiguator` is also exposed; `disambiguate(tokens)` takes a
pre-tokenized list. `TokenResult.analyzed` is `False` for tokens the analyzer
could not analyze (lemma/stem/root then fall back to the token).

## Command line

Installing the package also provides a `farahidi` command with two subcommands
mirroring the two entry points:

```bash
# Layer 1 — every analysis of each word
farahidi analyze الكتاب لأنهم

# Layer 2 — one disambiguated result per token, in context
farahidi text "ذهب الولد إلى المدرسة"
# ذهب     ذَهَبَ    ذَهَب    ذهب
# الولد   وَلَد     وَلَد    ولد
# إلى     إِلَى     إِلَى    -
# المدرسة مَدْرَسَة مَدْرَسَة درس
```

Add `--json` to either subcommand for JSON Lines output (one object per word for
`analyze`, one per token for `text`). With no positional argument both read from
stdin — `analyze` splits it on whitespace into words, `text` treats it as the
text to tokenize:

```bash
echo "مدرسة كتاب" | farahidi analyze --json
```

## Scope

- **Layer 1** — out-of-context analysis of a single word (`analyze`), returning
  all candidates ranked by frequency.
- **Layer 2** — in-context disambiguation (`analyze_text` / `Disambiguator`), a
  faithful port of AlKhalil's shipped `ADATAnalyzer` (lemmatizer + light/heavy
  stemmer). The chosen lemma is exact; the stem/root are then selected by corpus
  frequency among that lemma's analyses. On exact frequency ties the pick depends
  on analysis enumeration order, which can differ from the Java reference (its
  decoder draws stems/roots from a `HashSet`); the lemma decode is unaffected.

`farahidi` is a **morphological analyzer** — it ports AlKhalil Morpho Sys 2 in full
(both shipped layers). It is *not* a POS tagger or a syntactic/dependency parser;
those are separate systems that consume an analyzer's output and are out of scope.

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
reference with `tools/gen_golden.py`: `--mode words` (Layer 1, via
`AlkhalilGolden.java`) and `--mode sentences` (Layer 2, via
`AlkhalilSentenceGolden.java`).
