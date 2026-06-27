"""Layer-1 (out-of-context) morphological analysis — port of AlKhalil's
``AlKhalil2Analyzer.processToken`` and the verbal/nominal/propernoun/toolword/
exceptional analyzers.

The pipeline per word: normalize → exceptional lookup (short-circuits) →
segment into proclitic+stem+enclitic → for each segment run the category
analyzers (gated by clitic ``classe``) → resolve the ``Formulas`` join → assemble
:class:`~farahidi.models.Analysis` candidates. Results are returned in pipeline
order; :func:`farahidi.analyze` sorts them by ``priority``.
"""

from __future__ import annotations

import re

from . import normalize as N
from .clitics import Segment, get_lists_segment
from .lexicon import Lexicon
from .models import Analysis
from .pos import decode_noun, decode_verb
from .vowelize import vowelize

_NUMBERED = "123456789"


def _fmt_freq(value: float) -> str:
    """Match Java ``DecimalFormat`` with 10 fixed fraction digits."""
    return f"{value:.10f}"


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
) -> Analysis:
    """Replicates the AlKhalil ``Result`` constructor, including its stem
    recomputation from root + diac pattern."""
    dps = N.remove_last_diacritics(diac_pattern_stem)
    if root not in ("#", "-") and dps != "-":
        stem = N.word_from_root_and_pattern(root, dps)
    return Analysis(
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
    )


class Analyzer:
    """Reusable analyzer. Construct once and call :meth:`process_token` /
    :meth:`analyze` repeatedly; the bundled tables load lazily and are shared."""

    def __init__(self) -> None:
        self.lex = Lexicon()
        self._verb_cache: dict[str, dict] = {}
        self._noun_cache: dict[str, dict] = {}

    # ------------------------------------------------------------------ API
    def analyze(self, word: str) -> list[Analysis]:
        """All analyses of ``word``, sorted by ``priority`` (descending)."""
        results = self.process_token(word)
        return sorted(results, key=lambda a: a.priority, reverse=True)

    def process_token(self, word: str) -> list[Analysis]:
        """Port of ``processToken`` — analyses in pipeline order (unsorted)."""
        lex = self.lex
        unvoweled = N.remove_all_diacritics(word)
        normalized = N.correct_erreur(word)

        exc = self._analyze_exceptional(normalized, unvoweled)
        if exc:
            return exc

        segments = get_lists_segment(lex, unvoweled)
        results: list[Analysis] = []
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
    def _filtre_hamza(normalized_word: str, results: list[Analysis]) -> list[Analysis]:
        hamza = N.type_hamza(normalized_word)
        if hamza == "":
            return results
        return [r for r in results if hamza in r.stem]

    # ----------------------------------------------------------- exceptional
    def _analyze_exceptional(self, normalized_word: str, unvoweled_word: str) -> list[Analysis]:
        ew = self.lex.map("exceptional").get(unvoweled_word)
        if ew is None:
            return []
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
            )
        ]

    # ------------------------------------------------------------- toolwords
    def _analyze_toolwords(
        self, normalized_word: str, unvoweled_word: str, seg: Segment
    ) -> list[Analysis]:
        lex = self.lex
        stem = seg.stem
        unv = lex.map("toolwords_unvoweled").get(stem)
        if unv is None:
            return []
        proc = seg.proclitic
        enc = seg.enclitic
        voweled_list = lex.list("toolwords_voweled")
        pos_list = lex.list("toolwords_pos")
        out: list[Analysis] = []
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
                    )
                )
        return out

    # ------------------------------------------------------------ propernoun
    def _analyze_propernoun(
        self, normalized_word: str, unvoweled_word: str, seg: Segment
    ) -> list[Analysis]:
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
        out: list[Analysis] = []
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
    def _analyze_verbal(self, normalized_word: str, seg: Segment) -> list[Analysis]:
        stem = seg.stem
        proc_class = seg.proclitic.classe
        enc_class = seg.enclitic.classe
        if not (1 <= len(stem) <= 9) or "N" in proc_class or "N" in enc_class:
            return []
        lex = self.lex
        solutions = self._possible_solutions(seg, "Verbs", self._verb_cache)
        imap = self._all_root_formulas(solutions)
        out: list[Analysis] = []
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
                sol_arr = self._verbal_interpret(
                    seg, feats["Type"], feats["Person"], feats["Person2"],
                    feats["Emphasized"], cm,
                )
                stem_h = N.correct_stem_hamza(seg.stem)
                freq = (diac_freq + canonic_freq + lemma_freq + lemmapattern_freq + pos_freq) / 5.0
                priority = _fmt_freq(freq)
                out.append(
                    _make_analysis(
                        voweled_word, sol_arr[0], stem_h, feats["partofspeech"], diac,
                        canonic_pattern, lemma, lemmapattern, s_root, cm, sol_arr[3], priority,
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
        result = [""] * 7
        if seg.proclitic.voweledform == "":
            prefix1 = "#"
            result[5] = "#"
        else:
            prefix1 = seg.proclitic.voweledform + "|" + (seg.proclitic.desc or "")
            result[5] = seg.proclitic.voweledform
        if seg.enclitic.voweledform == "":
            suffix1 = "#"
            result[6] = "#"
        else:
            suffix1 = seg.enclitic.voweledform + "|" + (seg.enclitic.desc or "")
            result[6] = seg.enclitic.voweledform
        prefix = self._proclitic_value(type_, person, person2)
        suffix = self._enclitic_value(type_, person, person2, emphasized, casemood)
        result[4] = "2"
        if prefix != "":
            result[0] = prefix if prefix1 == "#" else prefix1 + "+" + prefix
        else:
            result[0] = prefix1
        if suffix != "":
            result[3] = suffix if suffix1 == "#" else suffix + "+" + suffix1
        else:
            result[3] = suffix1
        return result

    @staticmethod
    def _proclitic_value(type_, person, person2):
        if type_ == "مضارع":
            if person == "مخاطب":
                return "ت|حرف المضارعة"
            if person2 == "أنا":
                return "أ|حرف المضارعة"
            if person2 == "نحن":
                return "ن|حرف المضارعة"
            if person2 == "هي":
                return "ت|تاء الغائبة"
            if person2 == "هما(ة)":
                return "ت|حرف المضارعة"
            return "ي|حرف المضارعة"
        return ""

    @staticmethod
    def _enclitic_value(type_, person, person2, emphasized, casemood):
        if emphasized == "مؤكد":
            return "ن|نون التوكيد" if person == "مخاطب" else ""
        if type_ == "أمر":
            if person == "مخاطب" and person2 != "أنتَ":
                if person2 == "أنتِ":
                    return "ي|ياء المخاطبة"
                if person2 == "أنتما":
                    return "ا|ألف المثنى"
                if person2 == "أنتم":
                    return "وا|واو الجماعة"
                if person2 == "أنتن":
                    return "ن|نون النسوة"
                return ""
            return ""
        if type_ == "ماض":
            table = {
                "أنا": "ت|تاء المتكلم",
                "نحن": "نا|نون المتكلمين",
                "أنتَ": "ت|تاء المخاطب",
                "أنتِ": "ت|تاء المخاطبة",
                "أنتما": "تما|تاء المخاطبين",
                "أنتم": "تم|تاء المخاطبين",
                "أنتن": "تن|تاء المخاطبات",
                "هي": "ت|تاء التأنيث الساكنة",
                "هما": "ا|ألف الاثنين",
                "هما(ة)": "تا|تاء التأنيت وألف الاثنين",
                "هم": "وا|واو الجماعة",
                "هن": "ن|نون النسوة",
            }
            return table.get(person2, "")
        if type_ == "مضارع":
            if person2 in ("هن", "أنتن"):
                return "ن|نون النسوة"
            if person2 == "أنتِ":
                return "ين|ياء المخاطبة والنون علامة الرفع" if casemood == "مرفوع" else "ي|ياء المخاطبة"
            if person2 in ("أنتما", "هما(ة)", "هما"):
                return "ان|ألف المثنى والنون علامة الرفع" if casemood == "مرفوع" else "ا|ألف المثنى"
            if person2 in ("أنتم", "هم"):
                return "ون|واو الجماعة والنون علامة الرفع" if casemood == "مرفوع" else "وا|واو الجماعة"
            return ""
        return ""

    # -------------------------------------------------------------- nominal
    def _analyze_nominal(self, normalized_word: str, seg: Segment) -> list[Analysis]:
        stem = seg.stem
        proc_class = seg.proclitic.classe
        enc_class = seg.enclitic.classe
        if not (2 <= len(stem) <= 11) or "V" in proc_class or "V" in enc_class:
            return []
        lex = self.lex
        solutions = self._possible_solutions(seg, "Nouns", self._noun_cache)
        imap = self._all_root_formulas(solutions)
        out: list[Analysis] = []
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
                sol_arr, possible = self._nominal_interpret(
                    seg, feats["Number"], feats["Gender"], feats["Definit"], canonic_pattern
                )
                if not possible:
                    continue
                pos_str = "|".join(
                    [feats["Main"], feats["Type"], feats["Number"], feats["Gender"], sol_arr[2]]
                )
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
                        voweled_word, sol_arr[0], stem_h, pos_str, diac, canonic_pattern,
                        lemma, lemmapattern, s_root, t or cm, sol_arr[3], priority,
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
        un_diac = N.remove_all_diacritics(canonic_pattern)
        result = [""] * 7
        proc_class = seg.proclitic.classe
        prefix = ""
        suffix = ""
        passe = True
        possible = True
        if seg.proclitic.voweledform == "":
            result[0] = "#"
            result[5] = "#"
        else:
            result[0] = seg.proclitic.voweledform + ": " + (seg.proclitic.desc or "")
            result[5] = seg.proclitic.voweledform
        if seg.enclitic.voweledform == "":
            result[3] = "#"
            result[6] = "#"
        else:
            result[3] = seg.enclitic.voweledform + ": " + (seg.enclitic.desc or "")
            result[6] = seg.enclitic.voweledform
        st = seg.stem
        if gender == "مؤنث" and number == "مفرد" and st.endswith("ة"):
            suffix = "ة: تاء التأنيث"
            passe = True
        elif gender == "مؤنث" and number == "مثنى":
            if st.endswith("تان"):
                suffix = "ة: تاء التأنيث + ان: علامة الإعراب"
                passe = True
            elif st.endswith("تين"):
                suffix = "ة: تاء التأنيث + ين: علامة الإعراب"
                passe = True
            elif st.endswith("تا"):
                suffix = "ة: تاء التأنيث + ا: علامة الإعراب"
                passe = False
            elif st.endswith("تي"):
                suffix = "ة: تاء التأنيث + ي: علامة الإعراب"
                passe = False
        elif gender == "مؤنث" and number == "جمع":
            if st.endswith("ات"):
                suffix = "ات: تاء التأنيث"
                passe = True
        elif gender == "مذكر" and number == "مثنى":
            if st.endswith("ان"):
                suffix = "ان: علامة الإعراب"
                passe = True
            elif st.endswith("ين"):
                suffix = "ين: علامة الإعراب"
                passe = True
            elif st.endswith("ا"):
                suffix = "ا: علامة الإعراب"
                passe = False
            elif st.endswith("ي"):
                suffix = "ي: علامة الإعراب"
                passe = False
        elif un_diac != "مفاعل" and canonic_pattern != "فَعَالِي" and gender == "مذكر" and number == "جمع":
            if st.endswith("ون"):
                suffix = "ون: علامة الإعراب"
                passe = True
            elif st.endswith("ين"):
                suffix = "ين: علامة الإعراب"
                passe = True
            elif st.endswith("و"):
                suffix = "و: علامة الإعراب"
                passe = False
            elif st.endswith("ي"):
                suffix = "ي: علامة الإعراب"
                passe = False
        if proc_class in ("N1", "N2", "N3", "N5"):
            if passe:
                result[2] = "معرف"
            else:
                result[2] = ""
                possible = False
        else:
            result[2] = definit
        result[4] = "1"
        if result[0] == "#" and prefix != "":
            result[0] = prefix
        elif result[0] != "#" and prefix != "":
            result[0] = result[0] + " + " + prefix
        if result[3] == "#" and suffix != "":
            result[3] = suffix
        elif result[3] != "#" and suffix != "":
            result[3] = suffix + " + " + result[3]
        return result, possible
