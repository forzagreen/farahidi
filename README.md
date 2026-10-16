# farahidi

[![PyPI](https://img.shields.io/pypi/v/farahidi)](https://pypi.org/project/farahidi/)
[![Python versions](https://img.shields.io/pypi/pyversions/farahidi)](https://pypi.org/project/farahidi/)
[![CI](https://github.com/forzagreen/farahidi/actions/workflows/ci.yml/badge.svg)](https://github.com/forzagreen/farahidi/actions/workflows/ci.yml)
[![License](https://img.shields.io/pypi/l/farahidi)](LICENSE)

**Arabic morphological analyzer for Python** — a pure-Python re-implementation of
[AlKhalil Morpho Sys 2](https://alkhalil.oujda-nlp-team.net/AlKhalil-MorphoSys.php)
(Oujda NLP Team).

Given an Arabic word, `farahidi` returns every valid morphological analysis —
**root, lemma, stem, pattern (wazn), part of speech with structured features, and
segmented clitics/affixes** — ranked by corpus frequency. The syntactic
case/mood endings (الإعراب) are kept apart from the morphology: each analysis
nests its possible *inflections* instead of being repeated once per ending.

- **Pure Python, zero dependencies.** Works on CPython 3.11 – 3.14.
- **Offline.** The full lexicon plus the in-context language model ship compressed
  inside the wheel (~11 MB); nothing is downloaded at runtime.
- **Faithful.** Output is validated against the original Java `AlKhalil2Analyzer`
  (single-word) and `ADATAnalyzer` (in-context).

This is the Python implementation. A 1:1 JavaScript / TypeScript port lives at
[`farahidi-js`](https://github.com/forzagreen/farahidi-js), with a live
[in-browser demo](https://forzagreen.github.io/farahidi-js/). Both re-implement the
original Java [AlKhalil Morpho Sys 2](https://alkhalil.oujda-nlp-team.net/AlKhalil-MorphoSys.php)
by the Oujda NLP Team.

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

for a in farahidi.analyze("بالمدرسة"):
    print(a.diacritized, a.lemma, a.root, a.pos, a.type, a.proclitics)
# بِالْمِدْرَسَة مِدْرَس درس اسم اسم آلة (Affix(form='بِال', description='حرف الجر+ال:التعريف'),)
# بِالْمُدَرَّسَة مُدَرَّس درس اسم اسم مفعول (Affix(form='بِال', description='حرف الجر+ال:التعريف'),)
# ...
```

`analyze()` returns a list of `Analysis` objects — one per **morphological
reading** of the word, sorted by `score` (most frequent first). All labels are
Arabic strings as found in the AlKhalil lexicon; `None` means "not applicable"
(a particle has no root, a noun has no mood, …).

| field | meaning |
|---|---|
| `diacritized` | the word with its diacritics, *without* the case/mood ending (`عَنْدَلِيب`, `يَكْتُب`) |
| `lemma` / `root` / `stem` | dictionary form, 3- or 4-letter root, clitic-free stem |
| `pattern` / `lemma_pattern` | canonical patterns (wazn) of the stem and the lemma |
| `pos` / `type` | part of speech (`اسم` / `فعل` / `حرف`) and sub-type (`اسم فاعل`, `مصدر أصلي`, `جر`, `اسم علم` …) |
| `gender` / `number` | noun features (`مذكر` / `مؤنث`, `مفرد` / `مثنى` / `جمع`) |
| `tense` / `voice` / `person` / `pronoun` / `transitivity` / `augmentation` / `emphatic` | verb features (`ماض` / `مضارع` / `أمر`, `معلوم` / `مجهول`, `غائب` …, the subject pronoun `هو` / `أنتَ` / …, `لازم` / `متعد`, `مجرد` / `مزيد`, نون التوكيد) |
| `proclitics` / `prefixes` / `suffixes` / `enclitics` | segmentation around the stem as `Affix(form, description)` tuples: clitics (`وَ`, `بِ`, `ال`, attached pronouns) and inflectional affixes (the مضارع prefix, `ة`, `ان`, `وا` …) |
| `score` | out-of-context ranking weight, higher = more frequent |
| `inflections` | the إعراب variants of this reading (below) |

### Morphology vs. syntax (الإعراب)

The case ending of a noun and the mood ending of a verb depend on the word's role
in a sentence, not on its morphology, so they do not multiply the results. A bare
`عندليب` is **one** analysis; its five possible endings are nested as
`Inflection` objects, best first:

```python
>>> a, = farahidi.analyze("عندليب")
>>> a.diacritized, a.pos, a.type, a.root
('عَنْدَلِيب', 'اسم', 'اسم جامد', 'عندل')
>>> for i in a.inflections:
...     print(i.diacritized, i.case, i.state)
عَنْدَلِيبٌ مرفوع نكرة
عَنْدَلِيبٍ مجرور نكرة
عَنْدَلِيبَ منصوب مضاف
عَنْدَلِيبُ مرفوع مضاف
عَنْدَلِيبِ مجرور مضاف
```

Each `Inflection` carries the fully vowelled `diacritized` form, `case` (nouns:
`مرفوع` / `منصوب` / `مجرور`) or `mood` (verbs: `مرفوع` / `منصوب` / `مجزوم`), the
noun's definiteness `state` (`نكرة` / `معرف بأل` / `مضاف` …) and its own `score`.
Indeclinable words (particles, past and imperative verbs) have exactly one
inflection with `case`/`mood` `None`. To get the old one-row-per-ending view,
iterate `for a in analyses for i in a.inflections`.

`Analysis.to_dict()` gives a plain nested dict (JSON-serializable). For repeated
analysis, build one reusable analyzer (the lexicon loads lazily and is shared):

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
pre-tokenized list and `tokenize(text)` exposes the sentence/word splitter.
`TokenResult.root` is `None` when the chosen reading has no root (particles).
`TokenResult.analyzed` is `False` for tokens the analyzer could not analyze
(lemma/stem then fall back to the token, root is `None`).

## Command line

Installing the package also provides a `farahidi` command with two subcommands
mirroring the two entry points:

```bash
# Layer 1 — every morphological analysis of each word
farahidi analyze الكتاب لأنهم

# ... one row per إعراب variant (case/mood, state, fully vowelled form) instead
farahidi analyze عندليب --inflections --format table

# Layer 2 — one disambiguated result per token, in context
farahidi text "ذهب الولد إلى المدرسة" --format table
# token    lemma  stem   root  analyzed
# -------  -----  -----  ----  --------
# ذهب      ذَهَبَ    ذَهَب    ذهب   true
# الولد    وَلَد    وَلَد    ولد   true
# إلى      إِلَى    إِلَى          true
# المدرسة  مَدْرَسَة  مَدْرَسَة  درس   true
```

Pick the output with `-f/--format`:

| format | description |
|---|---|
| `raw` *(default)* | TAB-separated, one record per line, no header — pipe to `cut`/`awk` |
| `table` | aligned columns with a header (best-effort: Arabic combining marks are measured correctly, but RTL terminals may still reorder cells) |
| `json` | JSON Lines — `analyze` nests every analysis (with its `inflections`) under its word; `text` emits one token result per line |
| `csv` | RFC-4180 with a header row — open in a spreadsheet or load with pandas |

The flat formats (`raw`/`table`/`csv`) share one column schema and omit the
inflections unless `-i/--inflections` is given; `json` keeps the nested
structure. With no positional argument both subcommands read from stdin —
`analyze` splits it on whitespace into words, `text` treats it as the text to
tokenize:

```bash
echo "مدرسة كتاب" | farahidi analyze -f csv
```

## Scope

- **Layer 1** — out-of-context analysis of a single word (`analyze`), returning
  all morphological readings ranked by frequency, each with its possible إعراب
  endings nested as inflections. The underlying engine is the full AlKhalil
  pipeline; its raw one-record-per-ending output is what the golden parity
  suite compares to the Java reference.
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
