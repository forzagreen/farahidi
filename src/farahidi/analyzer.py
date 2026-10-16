"""Layer-1 (out-of-context) morphological analysis — port of AlKhalil's
``AlKhalil2Analyzer.processToken`` and the verbal/nominal/propernoun/toolword/
exceptional analyzers.

The pipeline per word: normalize → exceptional lookup (short-circuits) →
segment into proclitic+stem+enclitic → for each segment run the category
analyzers (gated by clitic ``classe``) → resolve the ``Formulas`` join → assemble
:class:`RawAnalysis` records, one per *(reading × إعراب ending)* exactly as the
Java ``Result`` list (this is what the golden parity suite checks).
:meth:`Analyzer.analyze` then collapses them into the public
:class:`~farahidi.models.Analysis` objects (see :mod:`farahidi.morphology`).
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from . import normalize as N
from .clitics import Clitic, Segment, get_lists_segment
from .lexicon import Lexicon
from .models import Affix, Analysis, Inflection
from .morphology import collapse, parse_pos_label
from .pos import decode_noun, decode_verb
from .vowelize import vowelize

_NUMBERED = "123456789"


def _fmt_freq(value: float) -> str:
    """Match Java ``DecimalFormat`` with 10 fixed fraction digits."""
    return f"{value:.10f}"


@dataclass(frozen=True, slots=True)
class RawAnalysis:
    """Internal: AlKhalil's 12-field ``Result`` record for one *(reading ×
    إعراب ending)*, plus the structured pieces the public model is built from.

    The twelve string fields are byte-for-byte what the Java reference emits
    (``"-"`` = not applicable, ``"#"`` = absent clitic, ``priority`` formatted to
    10 decimals) and are what ``tests/test_golden.py`` compares. ``morph`` is the
    :class:`Analysis` *template* of the reading (``score`` 0, no inflections) and
    ``inflection`` this record's realization; :func:`farahidi.morphology.collapse`
    groups records by ``morph``.
    """

    voweled_word: str
    proclitic: str
    stem: str
    part_of_speech: str
    diac_pattern_stem: str
    pattern_stem: str
    lemma: str
    pattern_lemma: str
    root: str
    case_or_mood: str
    enclitic: str
    priority: str
    morph: Analysis
    inflection: Inflection


def _opt(value: str | None) -> str | None:
    """AlKhalil's ``"-"`` / ``"#"`` / empty placeholders → ``None``."""
    return None if value in (None, "", "-", "#") else value


def _clitic_affixes(clitic: Clitic) -> tuple[Affix, ...]:
    return (Affix(clitic.voweledform, _opt(clitic.desc)),) if clitic.voweledform else ()


def _make_analysis(
    voweled: str,
    proclitic: str,
    stem: str,
    pos: str,
    diac_pattern_stem: str,
    pattern_stem: str,
    lemma: str,
    pattern_lemma: str,
    root: str,
    casemood: str,
    enclitic: str,
    priority: str,
    *,
    features: dict[str, str | None],
    emphatic: bool | None = None,
    state: str | None = None,
    proclitics: tuple[Affix, ...] = (),
    prefixes: tuple[Affix, ...] = (),
    suffixes: tuple[Affix, ...] = (),
    enclitics: tuple[Affix, ...] = (),
) -> RawAnalysis:
    """Replicates the AlKhalil ``Result`` constructor (including its stem
    recomputation from root + diac pattern) and derives the public-model pieces.

    ``features`` carries ``pos``/``type``/``tense``/``gender``/``number``/
    ``person``/``pronoun``/``voice``/``transitivity``/``augmentation`` (missing
    keys → ``None``). A record with an إعراب ending (``casemood != "-"``) has that
    ending stripped from the morphological ``diacritized``/``stem``/``pattern``;
    the full form is kept on the :class:`Inflection`.
    """
    dps = N.remove_last_diacritics(diac_pattern_stem)
    if root not in ("#", "-") and dps != "-":
        stem = N.word_from_root_and_pattern(root, dps)
    cm = _opt(casemood)
    main_pos = features["pos"]
    pattern = _opt(pattern_stem)
    if cm is not None:
        voweled_m = N.strip_case_ending(voweled)
        stem_m = N.strip_case_ending(stem)
        # In a pattern the alif after tanween fatḥ is only the tanween's carrier
        # (فِعَالًا → فِعَال), unlike in the word, where the letter is kept.
        if pattern is not None:
            pattern = N.strip_case_ending(pattern[:-1] if pattern.endswith("ًا") else pattern)
    else:
        voweled_m, stem_m = voweled, stem
    morph = Analysis(
        diacritized=voweled_m,
        lemma=lemma,
        root=_opt(root),
        stem=stem_m,
        pattern=pattern,
        lemma_pattern=_opt(pattern_lemma),
        pos=main_pos,
        type=features.get("type"),
        tense=features.get("tense"),
        gender=features.get("gender"),
        number=features.get("number"),
        person=features.get("person"),
        pronoun=features.get("pronoun"),
        voice=features.get("voice"),
        transitivity=features.get("transitivity"),
        augmentation=features.get("augmentation"),
        emphatic=emphatic,
        proclitics=proclitics,
        prefixes=prefixes,
        suffixes=suffixes,
        enclitics=enclitics,
        score=0.0,
        inflections=(),
    )
    inflection = Inflection(
        diacritized=voweled,
        case=cm if main_pos != "فعل" else None,
        mood=cm if main_pos == "فعل" else None,
        state=state,
        score=float(priority),
    )
    return RawAnalysis(
        voweled_word=voweled,
        proclitic=proclitic,
        stem=stem,
        part_of_speech=pos,
        diac_pattern_stem=dps,
        pattern_stem=pattern_stem,
        lemma=lemma,
        pattern_lemma=pattern_lemma,
        root=root,
        case_or_mood=casemood,
        enclitic=enclitic,
        priority=priority,
        morph=morph,
        inflection=inflection,
    )


class Analyzer:
    """Reusable Layer-1 analyzer. Construct once and call :meth:`analyze`
    repeatedly; the bundled tables load lazily and are shared."""

    def __init__(self) -> None:
        self.lex = Lexicon()
        self._verb_cache: dict[str, dict] = {}
        self._noun_cache: dict[str, dict] = {}

    # ------------------------------------------------------------------ API
    def analyze(self, word: str) -> list[Analysis]:
        """All morphological analyses of ``word``, best ``score`` first.

        Readings that differ only in their إعراب ending are returned once, with
        the endings nested under :attr:`~farahidi.models.Analysis.inflections`.
        """
        return collapse(self._process_token(word))

    def _process_token(self, word: str) -> list[RawAnalysis]:
        """Port of ``processToken`` — one raw record per *(reading × ending)*,
        in pipeline order (unsorted), exactly as the Java reference."""
        lex = self.lex
        unvoweled = N.remove_all_diacritics(word)
        normalized = N.correct_erreur(word)

        exc = self._analyze_exceptional(normalized, unvoweled)
        if exc:
            return exc

        segments = get_lists_segment(lex, unvoweled)
        results: list[RawAnalysis] = []
        for seg in segments:
            results.extend(self._analyze_propernoun(normalized, unvoweled, seg))
            results.extend(
                self._filtre_hamza(normalized, self._analyze_toolwords(normalized, unvoweled, seg))
            )
            results.extend(self._filtre_hamza(normalized, self._analyze_nominal(normalized, seg)))
            results.extend(self._filtre_hamza(normalized, self._analyze_verbal(normalized, seg)))

        if not results and normalized.endswith("ًا") and not normalized.endswith("ًّا"):
            normalized = re.sub("ًا$", "ًّا", normalized)
            for seg in segments:
                results.extend(self._analyze_propernoun(normalized, unvoweled, seg))
                results.extend(self._analyze_nominal(normalized, seg))
        return results

    # -------------------------------------------------------------- helpers
    @staticmethod
    def _filtre_hamza(normalized_word: str, results: list[RawAnalysis]) -> list[RawAnalysis]:
        hamza = N.type_hamza(normalized_word)
        if hamza == "":
            return results
        return [r for r in results if hamza in r.stem]

    # ----------------------------------------------------------- exceptional
    def _analyze_exceptional(self, normalized_word: str, unvoweled_word: str) -> list[RawAnalysis]:
        ew = self.lex.map("exceptional").get(unvoweled_word)
        if ew is None:
            return []
        proc = _opt(ew["proclitic"])
        enc = _opt(ew["enclitic"])
        return [
            _make_analysis(
                ew["voweledform"],
                ew["proclitic"],
                ew["stem"],
                ew["pos"],
                "-",
                "-",
                "الله",
                "-",
                "-",
                "-",
                ew["enclitic"],
                "1",
                features=parse_pos_label(ew["pos"]),
                proclitics=(Affix(proc),) if proc else (),
                enclitics=(Affix(enc),) if enc else (),
            )
        ]

    # ------------------------------------------------------------- toolwords
    def _analyze_toolwords(
        self, normalized_word: str, unvoweled_word: str, seg: Segment
    ) -> list[RawAnalysis]:
        lex = self.lex
        stem = seg.stem
        unv = lex.map("toolwords_unvoweled").get(stem)
        if unv is None:
            return []
        proc = seg.proclitic
        enc = seg.enclitic
        voweled_list = lex.list("toolwords_voweled")
        pos_list = lex.list("toolwords_pos")
        out: list[RawAnalysis] = []
        for sid in unv.split(" "):
            tw = voweled_list[int(sid) - 1]
            proc_class = tw["procClass"] or ""
            enc_class = tw["encClass"] or ""
            if seg.proclitic.classe not in proc_class or seg.enclitic.classe not in enc_class:
                continue
            twvow = tw["voweledform"]
            ends_i = twvow.endswith("ي") or twvow.endswith("يْ") or twvow.endswith("ِ")
            if enc.unvoweledform == "ه":
                enc.voweledform = "هِ" if ends_i else "هُ"
            elif enc.unvoweledform == "هما":
                enc.voweledform = "هِمَا" if ends_i else "هُمَا"
            elif enc.unvoweledform == "هم":
                enc.voweledform = "هِمْ" if ends_i else "هُمْ"
            elif enc.unvoweledform == "هن":
                enc.voweledform = "هِنَّ" if ends_i else "هُنَّ"
            lemma = tw["lemma"]
            root_raw = tw["root"] or ""
            root = root_raw if root_raw == N.remove_all_diacritics(root_raw) else "-"
            if any(c in proc_class for c in ("N1", "N2", "N3", "N5")):
                res = twvow
                if N.is_solar(res[0]):
                    voweled = proc.voweledform + "ْ" + res[0] + "ّ" + res[1:] + enc.voweledform
                else:
                    voweled = proc.voweledform + "ْ" + res + enc.voweledform
            else:
                voweled = proc.voweledform + twvow + enc.voweledform
            pf = "#" if proc.voweledform == "" else proc.voweledform + " : " + (proc.desc or "")
            sf = "#" if enc.voweledform == "" else enc.voweledform + " : " + (enc.desc or "")
            type_str = pos_list[int(tw["pos"]) - 1]
            voweled = voweled.replace("لَلْلّ", "لَلّ").replace("لِلْلّ", "لِلّ")
            voweled = voweled.replace("لِالّ", "لِلّ").replace("لَالّ", "لَلّ")
            if not N.not_compatible(normalized_word, voweled):
                out.append(
                    _make_analysis(
                        voweled,
                        pf,
                        N.remove_last_diacritics(twvow),
                        type_str,
                        "-",
                        "-",
                        lemma,
                        "-",
                        root,
                        "-",
                        sf,
                        "0.0001100101",
                        features=parse_pos_label(type_str),
                        proclitics=_clitic_affixes(proc),
                        enclitics=_clitic_affixes(enc),
                    )
                )
        return out

    # ------------------------------------------------------------ propernoun
    def _analyze_propernoun(
        self, normalized_word: str, unvoweled_word: str, seg: Segment
    ) -> list[RawAnalysis]:
        proc_class = seg.proclitic.classe
        enc_class = seg.enclitic.classe
        if "V" in proc_class or "V" in enc_class:
            return []
        lex = self.lex
        unv = lex.map("propernoun_unvoweled").get(seg.stem)
        if unv is None:
            return []
        voweled_list = lex.list("propernoun_voweled")
        pos_list = lex.list("propernoun_pos")
        casemood_list = lex.list("propernoun_casemood")
        proc = seg.proclitic
        enc = seg.enclitic
        out: list[RawAnalysis] = []
        for sid in unv.split(" "):
            ipn = int(sid)
            if ipn > len(voweled_list):
                continue
            pn = voweled_list[ipn - 1]
            pnvow = pn["vowform"]
            ends_i = pnvow.endswith("ي") or pnvow.endswith("يْ") or pnvow.endswith("ِ")
            if enc.unvoweledform == "ه":
                enc.voweledform = "هِ" if ends_i else "هُ"
            elif enc.unvoweledform == "هما":
                enc.voweledform = "هِمَا" if ends_i else "هُمَا"
            elif enc.unvoweledform == "هم":
                enc.voweledform = "هِمْ" if ends_i else "هُمْ"
            elif enc.unvoweledform == "هن":
                enc.voweledform = "هِنَّ" if ends_i else "هُنَّ"
            pf = proc.voweledform
            sf = enc.voweledform
            if proc.classe == "N4" and proc.unvoweledform.endswith("ل") and pnvow.startswith("ا"):
                val = pnvow
                if enc.unvoweledform != "":
                    val = val.replace("ة", "ت")
                voweled = pf + val[1:] + sf
            elif N.is_definit(proc.classe):
                res = pnvow
                if enc.unvoweledform != "":
                    res = res.replace("ة", "ت")
                if N.is_solar(res[0]):
                    voweled = pf + "ْ" + res[0] + "ّ" + res[1:] + sf
                else:
                    voweled = pf + "ْ" + res + sf
            else:
                res = pnvow
                if enc.unvoweledform != "":
                    res = res.replace("ة", "ت")
                voweled = pf + res + sf
            if N.not_compatible(normalized_word, voweled, seg, False):
                continue
            lemma = pn["lemma"]
            root_raw = pn["root"] or ""
            root = root_raw if root_raw == N.remove_all_diacritics(root_raw) else "-"
            pf_out = "#" if pf == "" else pf + " : " + (proc.desc or "")
            sf_out = "#" if sf == "" else sf + " : " + (enc.desc or "")
            pos = pos_list[int(pn["pos"]) - 1]
            type_str = "|".join(
                [pos["main"] or "", pos["type"] or "", pos["gender"] or "", pos["number"] or ""]
            )
            cas = casemood_list[int(pn["cas"]) - 1]["valAR"]
            if self._valid_propernoun(seg, cas, voweled):
                out.append(
                    _make_analysis(
                        voweled,
                        pf_out,
                        N.remove_last_diacritics(pnvow),
                        type_str,
                        "-",
                        "-",
                        lemma,
                        "-",
                        root,
                        cas,
                        sf_out,
                        "0.01100101",
                        features={
                            "pos": pos["main"],
                            "type": _opt(pos["type"]),
                            "gender": _opt(pos["gender"]),
                            "number": _opt(pos["number"]),
                        },
                        state=_opt(pos.get("definit")),
                        proclitics=_clitic_affixes(proc),
                        enclitics=_clitic_affixes(enc),
                    )
                )
        return out

    @staticmethod
    def _valid_propernoun(seg: Segment, caseormood: str, voweled: str) -> bool:
        pc = seg.proclitic.classe
        if ("ً" in voweled or "ٍ" in voweled or "ٌ" in voweled) and (
            seg.enclitic.unvoweledform != "" or N.is_definit(pc)
        ):
            return False
        if pc in ("N2", "C2", "C3") and caseormood == "مجرور":
            return False
        if pc in ("N4", "N5") and caseormood != "مجرور":
            return False
        return True

    # --------------------------------------------------------- derived join
    def _get_possible_roots(self, stem: str, rules: str, cat: str) -> set[str]:
        roots: set[str] = set()
        for rule in rules.split(" "):
            root_chars: list[str] = []
            for r in rule:
                if r in _NUMBERED:
                    c = stem[int(r) - 1]
                    root_chars.append("ء" if N.is_hamza(c) else c)
                else:
                    root_chars.append("ء" if N.is_hamza(r) else r)
            root = "".join(root_chars)
            if self.lex.contains_root(cat, root):
                roots.add(root)
        return roots

    def _get_info_result(self, id_root: str, id_pattern_stem: str, length: int, cat: str) -> list[dict]:
        result: list[dict] = []
        pattern_ids = set(id_pattern_stem.split(" "))
        formulas = self.lex.formulas(cat, length)
        for idr in id_root.split(" "):
            idx = int(idr)
            if not (0 < idx <= len(formulas)):
                continue
            f = formulas[idx - 1]
            if f["idDiacPatternStem"] in pattern_ids:
                result.append(f)
        return result

    def _possible_solutions(self, seg: Segment, cat: str, cache: dict) -> dict:
        stem1 = seg.stem
        if stem1 in cache:
            return cache[stem1]
        lex = self.lex
        stem = stem1[0] + N.normalize_hamza(stem1[1:]) if stem1 else stem1
        len_diac = len(stem)
        result: dict[str, dict] = {}
        for unv in lex.unvoweled_stems(cat, len_diac):
            s_unvoweled = unv["val"]
            s_unvoweled = s_unvoweled[0] + N.normalize_hamza(s_unvoweled[1:])
            if not N.is_diac_pattern(stem, s_unvoweled):
                continue
            iroots = self._get_possible_roots(stem, unv["rules"], cat)
            if not iroots:
                continue
            roots_map: dict[str, list[dict]] = {}
            add = False
            for root in iroots:
                val = N.word_from_root_and_pattern(root, s_unvoweled)
                root_ent = lex.root_entity(cat, root)
                if root_ent is None:
                    continue
                len_stem = len(seg.stem)
                id_root = root_ent.get(f"len{len_stem}") if 1 <= len_stem <= 12 else None
                if (
                    id_root
                    and N.normalize_hamza(val) == N.normalize_hamza(stem)
                ):
                    res = self._get_info_result(id_root, unv["ids"], len_stem, cat)
                    if res:
                        roots_map[root] = res
                        add = True
            if add:
                result[unv["val"]] = roots_map
        cache[stem1] = result
        return result

    @staticmethod
    def _all_root_formulas(solutions: dict) -> dict[str, list[dict]]:
        out: dict[str, dict[int, dict]] = {}
        for roots in solutions.values():
            for root, formulas in roots.items():
                bucket = out.setdefault(root, {})
                for f in formulas:
                    bucket[id(f)] = f
        return {root: list(b.values()) for root, b in out.items()}

    def _info_results(self, formula: dict, length: int, cat: str) -> list[str]:
        lex = self.lex
        out: list[str] = [""] * 10
        vd = lex.voweled_diac_stem(cat, length, int(formula["idDiacPatternStem"]))
        out[0] = vd["val"]
        out[1] = vd["freq"]
        clen, cid = formula["idCanonicPatternStem"].split(".")
        vd = lex.voweled_canonic_stem(cat, int(clen), int(cid))
        out[2] = vd["val"]
        out[3] = vd["freq"]
        llen, lid = formula["idDiacPatternLemma"].split(".")
        vd = lex.voweled_diac_lemma(cat, int(llen), int(lid))
        out[4] = vd["val"]
        out[5] = vd["freq"]
        plen, pid = formula["idCanonicPatternLemma"].split(".")
        vd = lex.voweled_canonic_lemma(cat, int(plen), int(pid))
        out[6] = vd["val"]
        out[7] = vd["freq"]
        out[8] = formula["idPartOfSpeech"]
        out[9] = formula["idCaseOrMood"]
        return out

    # -------------------------------------------------------------- verbal
    def _analyze_verbal(self, normalized_word: str, seg: Segment) -> list[RawAnalysis]:
        stem = seg.stem
        proc_class = seg.proclitic.classe
        enc_class = seg.enclitic.classe
        if not (1 <= len(stem) <= 9) or "N" in proc_class or "N" in enc_class:
            return []
        lex = self.lex
        solutions = self._possible_solutions(seg, "Verbs", self._verb_cache)
        imap = self._all_root_formulas(solutions)
        out: list[RawAnalysis] = []
        len_stem = len(seg.stem)
        for s_root, formulas in imap.items():
            for sol in formulas:
                info = self._info_results(sol, len_stem, "Verbs")
                diac = info[0]
                diac_freq = float(info[1])
                canonic_pattern = info[2]
                canonic_freq = float(info[3])
                lemma = N.word_from_root_and_pattern(s_root, info[4])
                lemma_freq = float(info[5])
                lemmapattern = info[6]
                lemmapattern_freq = float(info[7])
                idpos = int(info[8])
                feats = decode_verb(lex, idpos)
                pos_freq = float(feats["freq"])
                idcm = int(info[9])
                cm = lex.casemood("Verbs", idcm)["valAR"]
                voweled = vowelize(seg, diac)
                voweled_word = voweled[0]
                if not self._valid_verbal(
                    seg, voweled_word, normalized_word, feats["Type"], feats["Voice"],
                    feats["Person2"], cm, feats["Transitivity"],
                ):
                    continue
                proclitic_str, enclitic_str, prefix, suffix = self._verbal_interpret(
                    seg, feats["Type"], feats["Person"], feats["Person2"],
                    feats["Emphasized"], cm,
                )
                stem_h = N.correct_stem_hamza(seg.stem)
                freq = (diac_freq + canonic_freq + lemma_freq + lemmapattern_freq + pos_freq) / 5.0
                priority = _fmt_freq(freq)
                out.append(
                    _make_analysis(
                        voweled_word, proclitic_str, stem_h, feats["partofspeech"], diac,
                        canonic_pattern, lemma, lemmapattern, s_root, cm, enclitic_str, priority,
                        features={
                            "pos": feats["Main"],
                            "tense": feats["Type"],
                            "voice": feats["Voice"],
                            "person": feats["Person"],
                            "pronoun": feats["Person2"],
                            "transitivity": feats["Transitivity"],
                            "augmentation": feats["Augmented"],
                        },
                        emphatic=feats["Emphasized"] == "مؤكد",
                        proclitics=_clitic_affixes(seg.proclitic),
                        prefixes=(Affix(*prefix),) if prefix else (),
                        suffixes=(Affix(*suffix),) if suffix else (),
                        enclitics=_clitic_affixes(seg.enclitic),
                    )
                )
        return out

    @staticmethod
    def _valid_verbal(seg, voweled_word, normalized_word, type_, voice, person2, casemood, transitivity):
        pref = seg.proclitic.classe
        suff = seg.enclitic.classe
        if transitivity == "لازم" and seg.enclitic.unvoweledform != "":
            return False
        if pref == "V1" and type_ != "مضارع" and casemood != "مرفوع":
            return False
        if pref == "V2" and type_ != "مضارع" and casemood != "منصوب":
            return False
        if pref == "V3" and type_ != "مضارع" and casemood != "مجزوم":
            return False
        if pref == "C2" and type_ == "أمر":
            return False
        if suff in ("V2", "V3") and type_ == "أمر":
            return False
        if suff == "V4" and person2 != "أنتم":
            return False
        if N.not_compatible(normalized_word, voweled_word, seg, False):
            return False
        return True

    def _verbal_interpret(self, seg, type_, person, person2, emphasized, casemood):
        """Port of ``VerbalAnalyzerImpl``'s proclitic/enclitic column assembly.

        Returns ``(proclitic_str, enclitic_str, prefix, suffix)``: the two Java
        column strings (``form|desc`` items joined by ``+``: clitic then the
        مضارع prefix; subject suffix then clitic) plus the inflectional prefix /
        suffix as ``(form, desc)`` tuples (``None`` when absent)."""
        if seg.proclitic.voweledform == "":
            prefix1 = "#"
        else:
            prefix1 = seg.proclitic.voweledform + "|" + (seg.proclitic.desc or "")
        if seg.enclitic.voweledform == "":
            suffix1 = "#"
        else:
            suffix1 = seg.enclitic.voweledform + "|" + (seg.enclitic.desc or "")
        prefix = self._proclitic_value(type_, person, person2)
        suffix = self._enclitic_value(type_, person, person2, emphasized, casemood)
        if prefix is not None:
            p = "|".join(prefix)
            proclitic_str = p if prefix1 == "#" else prefix1 + "+" + p
        else:
            proclitic_str = prefix1
        if suffix is not None:
            s = "|".join(suffix)
            enclitic_str = s if suffix1 == "#" else s + "+" + suffix1
        else:
            enclitic_str = suffix1
        return proclitic_str, enclitic_str, prefix, suffix

    @staticmethod
    def _proclitic_value(type_, person, person2) -> tuple[str, str] | None:
        """The مضارع prefix letter and its label."""
        if type_ == "مضارع":
            if person == "مخاطب":
                return ("ت", "حرف المضارعة")
            if person2 == "أنا":
                return ("أ", "حرف المضارعة")
            if person2 == "نحن":
                return ("ن", "حرف المضارعة")
            if person2 == "هي":
                return ("ت", "تاء الغائبة")
            if person2 == "هما(ة)":
                return ("ت", "حرف المضارعة")
            return ("ي", "حرف المضارعة")
        return None

    @staticmethod
    def _enclitic_value(type_, person, person2, emphasized, casemood) -> tuple[str, str] | None:
        """The subject / emphasis suffix and its label."""
        if emphasized == "مؤكد":
            return ("ن", "نون التوكيد") if person == "مخاطب" else None
        if type_ == "أمر":
            if person == "مخاطب" and person2 != "أنتَ":
                if person2 == "أنتِ":
                    return ("ي", "ياء المخاطبة")
                if person2 == "أنتما":
                    return ("ا", "ألف المثنى")
                if person2 == "أنتم":
                    return ("وا", "واو الجماعة")
                if person2 == "أنتن":
                    return ("ن", "نون النسوة")
                return None
            return None
        if type_ == "ماض":
            table = {
                "أنا": ("ت", "تاء المتكلم"),
                "نحن": ("نا", "نون المتكلمين"),
                "أنتَ": ("ت", "تاء المخاطب"),
                "أنتِ": ("ت", "تاء المخاطبة"),
                "أنتما": ("تما", "تاء المخاطبين"),
                "أنتم": ("تم", "تاء المخاطبين"),
                "أنتن": ("تن", "تاء المخاطبات"),
                "هي": ("ت", "تاء التأنيث الساكنة"),
                "هما": ("ا", "ألف الاثنين"),
                "هما(ة)": ("تا", "تاء التأنيت وألف الاثنين"),
                "هم": ("وا", "واو الجماعة"),
                "هن": ("ن", "نون النسوة"),
            }
            return table.get(person2)
        if type_ == "مضارع":
            if person2 in ("هن", "أنتن"):
                return ("ن", "نون النسوة")
            if person2 == "أنتِ":
                if casemood == "مرفوع":
                    return ("ين", "ياء المخاطبة والنون علامة الرفع")
                return ("ي", "ياء المخاطبة")
            if person2 in ("أنتما", "هما(ة)", "هما"):
                if casemood == "مرفوع":
                    return ("ان", "ألف المثنى والنون علامة الرفع")
                return ("ا", "ألف المثنى")
            if person2 in ("أنتم", "هم"):
                if casemood == "مرفوع":
                    return ("ون", "واو الجماعة والنون علامة الرفع")
                return ("وا", "واو الجماعة")
            return None
        return None

    # -------------------------------------------------------------- nominal
    def _analyze_nominal(self, normalized_word: str, seg: Segment) -> list[RawAnalysis]:
        stem = seg.stem
        proc_class = seg.proclitic.classe
        enc_class = seg.enclitic.classe
        if not (2 <= len(stem) <= 11) or "V" in proc_class or "V" in enc_class:
            return []
        lex = self.lex
        solutions = self._possible_solutions(seg, "Nouns", self._noun_cache)
        imap = self._all_root_formulas(solutions)
        out: list[RawAnalysis] = []
        len_stem = len(seg.stem)
        for s_root, formulas in imap.items():
            for sol in formulas:
                info = self._info_results(sol, len_stem, "Nouns")
                diac = info[0]
                diac_freq = float(info[1])
                canonic_pattern = info[2]
                canonic_freq = float(info[3])
                lemma = N.word_from_root_and_pattern(s_root, info[4])
                lemma_freq = float(info[5])
                lemmapattern = info[6]
                lemmapattern_freq = float(info[7])
                idpos = int(info[8]) if info[8] is not None else 0
                feats = decode_noun(lex, idpos)
                pos_freq = float(feats["freq"])
                idcm = int(info[9])
                cm = lex.casemood("Nouns", idcm)["valAR"]
                voweled = vowelize(seg, diac)
                voweled_word = voweled[0]
                if feats["Number"] != "مثنى" and voweled_word.endswith("ءَانِ"):
                    voweled_word = voweled_word.replace("ءَانِ", "آنِ")
                voweled_word = voweled_word.replace("لَلْلّ", "لَلّ").replace("لِلْلّ", "لِلّ")
                proc_def = proc_class in ("N1", "N2", "N3", "N5")
                p_definit = True
                if feats["Definit"] == "معرف بأل" and not proc_def:
                    p_definit = False
                if proc_def and feats["Definit"] in (
                    "مضاف إلى معرفة", "مضاف إلى نكرة", "غير مضاف",
                ):
                    p_definit = False
                if not p_definit:
                    continue
                if not self._valid_nominal(seg, cm, voweled_word, normalized_word):
                    continue
                proclitic_str, enclitic_str, state, possible, suffixes = self._nominal_interpret(
                    seg, feats["Number"], feats["Gender"], feats["Definit"], canonic_pattern
                )
                if not possible:
                    continue
                pos_str = "|".join([feats["Main"], feats["Type"], feats["Number"], feats["Gender"], state])
                stem_h = N.correct_stem_hamza(seg.stem)
                freq = (diac_freq + canonic_freq + lemma_freq + lemmapattern_freq + pos_freq) / 5.0
                priority = _fmt_freq(freq)
                t = ""
                if (
                    proc_class in ("N4", "N5")
                    and cm == "منصوب"
                    and voweled_word == normalized_word
                ):
                    t = "مجرور"
                out.append(
                    _make_analysis(
                        voweled_word, proclitic_str, stem_h, pos_str, diac, canonic_pattern,
                        lemma, lemmapattern, s_root, t or cm, enclitic_str, priority,
                        features={
                            "pos": feats["Main"],
                            "type": feats["Type"],
                            "gender": feats["Gender"],
                            "number": feats["Number"],
                        },
                        state=_opt(state),
                        proclitics=_clitic_affixes(seg.proclitic),
                        suffixes=tuple(Affix(form, desc) for form, desc in suffixes),
                        enclitics=_clitic_affixes(seg.enclitic),
                    )
                )
        return out

    @staticmethod
    def _valid_nominal(seg, caseormood, voweled_word, normalized_word):
        pc = seg.proclitic.classe
        enc_unv = seg.enclitic.unvoweledform
        if ("ً" in voweled_word or "ٍ" in voweled_word or "ٌ" in voweled_word) and (
            enc_unv != "" or N.is_definit(pc)
        ):
            return False
        if pc in ("N2", "C2", "C3") and caseormood == "مجرور":
            return False
        if pc in ("N4", "N5") and caseormood != "مجرور" and voweled_word != normalized_word:
            return False
        return not N.not_compatible(normalized_word, voweled_word, seg, False)

    @staticmethod
    def _nominal_interpret(seg, number, gender, definit, canonic_pattern):
        """Port of ``NominalAnalyzerImpl``'s proclitic/enclitic column assembly.

        Returns ``(proclitic_str, enclitic_str, state, possible, suffixes)``: the
        two Java column strings (``form: desc`` items joined by `` + ``: the
        feminine / number suffixes then the enclitic), the definiteness state
        that ends the POS string, whether the reading is admissible, and the
        suffixes as ``(form, desc)`` tuples."""
        un_diac = N.remove_all_diacritics(canonic_pattern)
        proc_class = seg.proclitic.classe
        suffixes: list[tuple[str, str]] = []
        passe = True
        possible = True
        if seg.proclitic.voweledform == "":
            proclitic_str = "#"
        else:
            proclitic_str = seg.proclitic.voweledform + ": " + (seg.proclitic.desc or "")
        if seg.enclitic.voweledform == "":
            enclitic_str = "#"
        else:
            enclitic_str = seg.enclitic.voweledform + ": " + (seg.enclitic.desc or "")
        st = seg.stem
        ta = ("ة", "تاء التأنيث")
        if gender == "مؤنث" and number == "مفرد" and st.endswith("ة"):
            suffixes = [ta]
            passe = True
        elif gender == "مؤنث" and number == "مثنى":
            if st.endswith("تان"):
                suffixes = [ta, ("ان", "علامة الإعراب")]
                passe = True
            elif st.endswith("تين"):
                suffixes = [ta, ("ين", "علامة الإعراب")]
                passe = True
            elif st.endswith("تا"):
                suffixes = [ta, ("ا", "علامة الإعراب")]
                passe = False
            elif st.endswith("تي"):
                suffixes = [ta, ("ي", "علامة الإعراب")]
                passe = False
        elif gender == "مؤنث" and number == "جمع":
            if st.endswith("ات"):
                suffixes = [("ات", "تاء التأنيث")]
                passe = True
        elif gender == "مذكر" and number == "مثنى":
            if st.endswith("ان"):
                suffixes = [("ان", "علامة الإعراب")]
                passe = True
            elif st.endswith("ين"):
                suffixes = [("ين", "علامة الإعراب")]
                passe = True
            elif st.endswith("ا"):
                suffixes = [("ا", "علامة الإعراب")]
                passe = False
            elif st.endswith("ي"):
                suffixes = [("ي", "علامة الإعراب")]
                passe = False
        elif un_diac != "مفاعل" and canonic_pattern != "فَعَالِي" and gender == "مذكر" and number == "جمع":
            if st.endswith("ون"):
                suffixes = [("ون", "علامة الإعراب")]
                passe = True
            elif st.endswith("ين"):
                suffixes = [("ين", "علامة الإعراب")]
                passe = True
            elif st.endswith("و"):
                suffixes = [("و", "علامة الإعراب")]
                passe = False
            elif st.endswith("ي"):
                suffixes = [("ي", "علامة الإعراب")]
                passe = False
        if proc_class in ("N1", "N2", "N3", "N5"):
            if passe:
                state = "معرف"
            else:
                state = ""
                possible = False
        else:
            state = definit
        suffix = " + ".join(form + ": " + desc for form, desc in suffixes)
        if enclitic_str == "#" and suffix != "":
            enclitic_str = suffix
        elif enclitic_str != "#" and suffix != "":
            enclitic_str = suffix + " + " + enclitic_str
        return proclitic_str, enclitic_str, state, possible, suffixes
