"""Layer-2 in-context disambiguation — port of ``ADATAnalyzer``.

Picks one analysis per token across a sentence with the HMM-ish decoder AlKhalil
actually ships (``ADATAnalyzer.analyzed`` / ``analyzedToken``), **not** the unused
``Spline_model2.getArgMaxI`` path that ``ALKHALIL-ALGORITHM.md`` §2 originally
described. The "tag" of the HMM is a **lemma** (``ResultList.getAllLemmas`` —
dedup'd, in analysis order); the chosen lemma's best stem/root is then a separate
corpus-frequency arg-max (the light/heavy stemmer outputs).

Scores are **additive** (not log-probs): for each candidate ``lemma2`` of word
*i*, take over candidates ``lemma1`` of word *i-1* the max of
``A(lemma1→lemma2) + d2 + [start]``, then add ``B(word_i→lemma2)``.

Faithful-port note — AlKhalil's ``analyzed`` resets its accumulator
(``IMapResW1 = new HashMap<>()``) at the top of every step *before* reading it, so
for positions ``i ≥ 2`` the ``d2`` term is **always** the per-lemma backoff
(``mapLemma`` else ``1e-5``), never the previous path score. We reproduce that
exactly. Missing emission/transition entries also back off to ``mapLemma`` / ``1e-5``.
Ties keep the first (lowest-index) candidate, matching Java's strict ``>``.
"""

from __future__ import annotations

import re

from . import normalize as N
from .analyzer import Analyzer
from .lm import LanguageModel
from .models import TokenResult

BACKOFF = 1e-5  # unknown-lemma smoothing in analyzed() (Java literal 1.0E-5)
TOKEN_RESB = 1e-6  # constant resB added in analyzedToken() (Java literal 1.0E-6)
START_D = 0.5  # Java `D`
START_MAXN_DEFAULT = 13336.0  # Java default maxN (= the .lm S0 total)

# A word = one Arabic letter then letters/diacritics, per ArabicStringUtil
# .getPatternCompile. Sentences break on AlKhalil's separators + newline.
_WORD_RE = re.compile("[" + N.ALL_ARABIC + "][" + N.ALL_ARABIC + N.ALL_DIACRITICS + "]*")
_SENTENCE_SPLIT_RE = re.compile("[.!:،؟؛\n]")


def tokenize(text: str) -> list[list[str]]:
    """Split ``text`` into sentences of corrected Arabic-word tokens.

    Mirrors ``setTokenizationString``: kashida is stripped, words are matched by
    the letter pattern and run through ``correctErreur``; punctuation separators
    end a sentence (the HMM decodes each sentence independently)."""
    text = text.replace("ـ", "")
    sentences: list[list[str]] = []
    for chunk in _SENTENCE_SPLIT_RE.split(text):
        tokens = [N.correct_erreur(w) for w in _WORD_RE.findall(chunk)]
        if tokens:
            sentences.append(tokens)
    return sentences


class Disambiguator:
    """In-context analyzer. Build once and reuse; the lexicon and the (large)
    language model load lazily and are shared across calls."""

    def __init__(self, analyzer: Analyzer | None = None, lm: LanguageModel | None = None) -> None:
        self.analyzer = analyzer or Analyzer()
        self.lm = lm or LanguageModel()
        self._morph: dict[str, tuple[list[str], bool]] = {}

    # ------------------------------------------------------------ morphology
    def _lemmas(self, token: str) -> tuple[list[str], bool]:
        """``(lemmas, analyzed)`` for ``token`` — dedup'd lemma list in analysis
        order, mirroring ``getAllLemmas``. Unanalyzable → ``([token], False)``."""
        cached = self._morph.get(token)
        if cached is not None:
            return cached
        analyses = self.analyzer.process_token(token)
        if not analyses:
            res = ([token], False)
        else:
            seen: set[str] = set()
            lemmas: list[str] = []
            for a in analyses:
                if a.lemma not in seen:
                    seen.add(a.lemma)
                    lemmas.append(a.lemma)
            res = (lemmas, True)
        self._morph[token] = res
        return res

    def _backoff(self, lemma: str) -> float:
        return self.lm.map_lemma.get(lemma, BACKOFF)

    # ------------------------------------------------------------- start row
    def _start_matrix(self, lemmas: list[str]) -> dict[str, float]:
        """Port of the ``startMatrix`` block shared by analyzed/analyzedToken."""
        start = self.lm.start
        max_start = 1.0
        max_n = START_MAXN_DEFAULT
        som = 0.0
        raw: dict[str, float] = {}
        for idx, tag in enumerate(lemmas):
            x = 0.0
            if tag in start:
                total, freq = start[tag]
                max_n = total
                x = freq / total
                s = freq - START_D
                if idx == 0 or max_start < s:
                    max_start = s
            som = x if idx == 0 else som + x
            raw[tag] = x
        size = len(lemmas) or 1
        denom = som + max_start / max_n * size
        return {tag: (max_start / max_n + x) / denom for tag, x in raw.items()}

    # --------------------------------------------------------------- decode
    def disambiguate_lemmas(self, tokens: list[str]) -> list[str]:
        """One chosen lemma per token (parallel to ``tokens``)."""
        if not tokens:
            return []
        morph = {t: self._lemmas(t)[0] for t in tokens}
        if len(tokens) == 1:
            return self._analyzed_token(tokens[0], morph)
        return self._analyzed(tokens, morph)

    def _analyzed(self, tokens: list[str], morph: dict[str, list[str]]) -> list[str]:
        n = len(tokens)
        start_matrix = self._start_matrix(morph[tokens[0]])
        emission = self.lm.emission
        transition = self.lm.transition
        backpointers: dict[int, list[int]] = {}
        accum: dict[str, float] = {}  # IMapResW1 after each step (last word's scores)

        for i in range(1, n):
            # IMapResW1 reset (bug-for-bug): d2 for i>=2 is always backoff below.
            word1, word2 = tokens[i - 1], tokens[i]
            unv1, unv2 = N.remove_all_diacritics(word1), N.remove_all_diacritics(word2)
            lem1, lem2 = morph[word1], morph[word2]
            next_accum: dict[str, float] = {}
            il: list[int] = []
            for tag2 in lem2:
                d1 = 0.0
                k = 0
                for j, tag1 in enumerate(lem1):
                    couple = tag1 + ":" + tag2
                    a = transition.get(couple)
                    res_a = a if a is not None else self._backoff(tag1)
                    if i == 1:
                        b = emission.get(unv1 + ":" + tag1)
                        d2 = b if b is not None else self._backoff(tag1)
                        val = res_a + d2 + start_matrix[tag1]
                    else:
                        val = res_a + self._backoff(tag1)
                    if j == 0 or val > d1:
                        d1 = val
                        k = j
                b2 = emission.get(unv2 + ":" + tag2)
                res_b = b2 if b2 is not None else self._backoff(tag2)
                next_accum[tag2] = res_b + d1
                il.append(k)
            accum = next_accum
            backpointers[i] = il

        last = morph[tokens[n - 1]]
        max_val = 0.0
        imax = 0
        for j, tag in enumerate(last):
            val = accum[tag]
            if j == 0 or val > max_val:
                max_val = val
                imax = j
        chosen = [last[imax]]
        for i in range(n - 1, 0, -1):
            imax = backpointers[i][imax]
            chosen.append(morph[tokens[i - 1]][imax])
        chosen.reverse()
        return chosen

    def _analyzed_token(self, token: str, morph: dict[str, list[str]]) -> list[str]:
        """Single-token path. Note: Java iterates a ``HashMap`` keyset here, so
        its tie-break is order-dependent; we iterate analysis order instead, which
        is deterministic but may differ from Java on exact ties."""
        lemmas = morph[token]
        sm = self._start_matrix(lemmas)
        b = self.lm.emission.get(token)
        res_b = b if b is not None else TOKEN_RESB
        max_val = 0.0
        max_tag = ""
        for idx, tag in enumerate(lemmas):
            val = sm[tag] + res_b
            if idx == 0 or max_val < val:
                max_val = val
                max_tag = tag
        return [max_tag]

    # --------------------------------------------------------- stem / root
    def _select_by_freq(self, token: str, lemma: str, analyzed: bool, attr: str, freq_map: dict[str, int]) -> str:
        """Highest-corpus-frequency ``attr`` (``stem``/``root``) among analyses
        sharing ``lemma`` — port of ``getStems`` / ``getRoots`` (list order,
        first-on-tie). Unanalyzable token → the token itself."""
        if not analyzed:
            return token
        best: str | None = None
        best_val = 0
        for a in self.analyzer.process_token(token):
            if a.lemma == lemma:
                value = getattr(a, attr)
                val = freq_map.get(value, 0)
                if best is None or best_val < val:
                    best = value
                    best_val = val
        return best if best is not None else token

    # --------------------------------------------------------------- public
    def disambiguate(self, tokens: list[str]) -> list[TokenResult]:
        """Full per-token result: chosen lemma + best stem + best root."""
        if not tokens:
            return []
        lemmas = self.disambiguate_lemmas(tokens)
        out: list[TokenResult] = []
        for token, lemma in zip(tokens, lemmas, strict=True):
            analyzed = self._lemmas(token)[1]
            stem = self._select_by_freq(token, lemma, analyzed, "stem", self.lm.map_stem)
            root = self._select_by_freq(token, lemma, analyzed, "root", self.lm.map_root)
            out.append(
                TokenResult(
                    token=token,
                    lemma=lemma if analyzed else token,
                    stem=stem,
                    root=root,
                    analyzed=analyzed,
                )
            )
        return out

    def analyze_text(self, text: str) -> list[TokenResult]:
        """Tokenize ``text`` and disambiguate each sentence; flat token order."""
        out: list[TokenResult] = []
        for sentence in tokenize(text):
            out.extend(self.disambiguate(sentence))
        return out
