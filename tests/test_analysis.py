"""Tests for the public morphological model built on top of the AlKhalil port.

The golden suite checks the raw per-(reading × ending) records against the Java
reference; here we check what ``analyze()`` makes of them: readings collapsed
over their إعراب endings, structured features and affixes, ``None`` instead of
the ``"-"`` / ``"#"`` placeholders, float scores.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import farahidi
from farahidi import Affix, Analysis, Analyzer, Inflection
from farahidi.morphology import parse_pos_label

GOLDEN = Path(__file__).parent / "fixtures" / "golden.jsonl"


@pytest.fixture(scope="module")
def analyzer() -> Analyzer:
    return Analyzer()


# ---------------------------------------------------------------- collapsing
def test_andalib_is_one_reading_with_five_inflections():
    analyses = farahidi.analyze("عندليب")
    assert len(analyses) == 1
    a = analyses[0]
    assert a.diacritized == "عَنْدَلِيب"  # no case ending at the morphological level
    assert (a.lemma, a.root, a.stem) == ("عَنْدَلِيب", "عندل", "عَنْدَلِيب")
    assert (a.pattern, a.lemma_pattern) == ("فَعْلَلِيل", "فَعْلَلِيل")
    assert (a.pos, a.type, a.gender, a.number) == ("اسم", "اسم جامد", "مذكر", "مفرد")
    assert a.tense is None and a.person is None and a.voice is None
    assert not hasattr(a, "case") and not hasattr(a, "case_or_mood")
    assert {(i.diacritized, i.case, i.state) for i in a.inflections} == {
        ("عَنْدَلِيبٌ", "مرفوع", "نكرة"),
        ("عَنْدَلِيبٍ", "مجرور", "نكرة"),
        ("عَنْدَلِيبُ", "مرفوع", "مضاف"),
        ("عَنْدَلِيبَ", "منصوب", "مضاف"),
        ("عَنْدَلِيبِ", "مجرور", "مضاف"),
    }
    assert all(i.mood is None for i in a.inflections)
    assert a.score == max(i.score for i in a.inflections)


def test_inflections_cover_every_raw_record(analyzer):
    """Collapsing loses nothing: every vowelled form the port produces is an
    inflection of some analysis, and there are never more analyses than records."""
    words = [json.loads(line)["word"] for line in GOLDEN.open(encoding="utf-8") if line.strip()]
    for word in words:
        raw = analyzer._process_token(word)
        analyses = analyzer.analyze(word)
        assert len(analyses) <= len(raw)
        forms = {i.diacritized for a in analyses for i in a.inflections}
        assert forms == {r.voweled_word for r in raw}
        for a in analyses:
            assert a.inflections
            assert a.score == max(i.score for i in a.inflections)
            assert list(a.inflections) == sorted(a.inflections, key=lambda i: i.score, reverse=True)


def test_best_raw_record_is_in_a_top_scored_analysis(analyzer):
    words = [json.loads(line)["word"] for line in GOLDEN.open(encoding="utf-8") if line.strip()]
    for word in words:
        raw = analyzer._process_token(word)
        if not raw:
            continue
        best = max(raw, key=lambda r: r.priority)
        analyses = analyzer.analyze(word)
        top_score = analyses[0].score
        assert float(best.priority) == top_score
        assert any(a.score == top_score and a.lemma == best.lemma and (a.root or "-") == best.root for a in analyses)


def test_sorted_by_score_descending():
    for word in ("كتب", "لأنهم", "مدرسة"):
        scores = [a.score for a in farahidi.analyze(word)]
        assert scores == sorted(scores, reverse=True)
        assert all(isinstance(s, float) for s in scores)


def test_maqsur_noun_collapses_across_tanween_spelling():
    """إِلًى (نكرة) and إِلَى (مضاف) are one reading; the particle is another."""
    analyses = farahidi.analyze("إلى")
    particles = [a for a in analyses if a.pos == "حرف"]
    nouns = [a for a in analyses if a.pos == "اسم"]
    assert len(particles) == 1 and len(nouns) == 1
    p = particles[0]
    assert (p.type, p.root, p.pattern, p.lemma_pattern) == ("جر", None, None, None)
    assert p.inflections == (Inflection("إِلَى", None, None, None, p.score),)
    n = nouns[0]
    assert (n.diacritized, n.pattern) == ("إِلَى", "فِعَل")
    assert len(n.inflections) == 6
    assert {i.diacritized for i in n.inflections} == {"إِلًى", "إِلَى"}


def test_unanalyzable_word_gives_empty_list():
    assert farahidi.analyze("zzz") == []


# ------------------------------------------------------------------ features
def test_verb_features_and_affixes():
    analyses = farahidi.analyze("يكتبوا")
    assert analyses
    for a in analyses:
        assert a.pos == "فعل" and a.tense == "مضارع"
        assert a.type is None and a.gender is None and a.number is None
        assert a.voice in ("معلوم", "مجهول")
        assert a.augmentation in ("مجرد", "مزيد")
        assert a.emphatic is False
        assert a.prefixes == (Affix("ي", "حرف المضارعة"),)
        assert a.suffixes == (Affix("وا", "واو الجماعة"),)
        assert a.proclitics == () and a.enclitics == ()
        # The same written form is منصوب or مجزوم: two inflections, one reading.
        assert {i.mood for i in a.inflections} == {"منصوب", "مجزوم"}
        assert all(i.case is None and i.state is None for i in a.inflections)
    top = analyses[0]
    assert (top.lemma, top.root, top.person, top.pronoun) == ("كَتَبَ", "كتب", "غائب", "هم")


def test_indeclinable_verbs_keep_their_final_vowel():
    for a in farahidi.analyze("كتبوا"):
        assert a.tense in ("ماض", "أمر")
        assert len(a.inflections) == 1
        assert a.inflections[0].mood is None
        assert a.inflections[0].diacritized == a.diacritized
    assert "كَتَبُوا" in {a.diacritized for a in farahidi.analyze("كتبوا")}
    assert "قَالَ" in {a.diacritized for a in farahidi.analyze("قال") if a.pos == "فعل"}


def test_emphatic_verb():
    emphatic = [a for a in farahidi.analyze("لنكتبن") if a.emphatic]
    assert emphatic
    for a in emphatic:
        assert a.inflections[0].mood is None  # مبني with نون التوكيد
        assert a.proclitics and a.prefixes == (Affix("ن", "حرف المضارعة"),)


def test_clitics_and_nominal_suffixes_are_structured():
    for a in farahidi.analyze("بالمدرسة"):
        assert a.proclitics == (Affix("بِال", "حرف الجر+ال:التعريف"),)
        assert a.suffixes == (Affix("ة", "تاء التأنيث"),)
        assert a.prefixes == () and a.enclitics == ()
        assert a.inflections == (Inflection(a.diacritized + "ِ", "مجرور", None, "معرف", a.score),)
    duals = farahidi.analyze("معلمتان")
    assert duals and all(a.suffixes == (Affix("ة", "تاء التأنيث"), Affix("ان", "علامة الإعراب")) for a in duals)
    assert all(a.number == "مثنى" and a.gender == "مؤنث" for a in duals)
    enc = [a for a in farahidi.analyze("لأنهم") if a.pos == "حرف"]
    assert enc and enc[0].proclitics == (Affix("لَ", "حرف الابتداء"),)
    assert enc[0].enclitics == (Affix("هُمْ", "ضمير الغائبين"),)
    assert enc[0].type == "ناسخ" and enc[0].lemma == "أَن\u0651\u064e"


def test_proper_noun():
    a = farahidi.analyze("محمد")[0]
    assert (a.pos, a.type, a.root, a.pattern) == ("اسم", "اسم علم", None, None)
    assert a.diacritized == "مُحَم\u0651\u064eد" and a.number == "مفرد" and a.gender is None
    assert {(i.case, i.state) for i in a.inflections} == {
        ("مرفوع", "نكرة"),
        ("مجرور", "نكرة"),
        ("مرفوع", "مضاف"),
        ("منصوب", "مضاف"),
        ("مجرور", "مضاف"),
    }


def test_exceptional_allah():
    (a,) = farahidi.analyze("الله")
    assert (a.pos, a.type, a.lemma, a.root, a.score) == ("اسم", "اسم الجلالة", "الله", None, 1.0)
    assert a.inflections == (Inflection("الله", None, None, None, 1.0),)
    (b,) = farahidi.analyze("والله")
    assert b.proclitics == (Affix("وَ", None),) and b.enclitics == ()


def test_parse_pos_label():
    assert parse_pos_label("اسم|إشارة|مؤنث|جمع") == {
        "pos": "اسم",
        "type": "إشارة",
        "tense": None,
        "gender": "مؤنث",
        "number": "جمع",
        "person": None,
    }
    assert parse_pos_label("اسم|ضمير|الغائب")["person"] == "غائب"
    assert parse_pos_label("فعل|ماض|جامد") == {
        "pos": "فعل",
        "type": "جامد",
        "tense": "ماض",
        "gender": None,
        "number": None,
        "person": None,
    }
    assert parse_pos_label("اسم|فعل|ماض")["type"] == "فعل"
    assert parse_pos_label("حرف|")["type"] is None
    assert parse_pos_label("جار ومجرور")["pos"] == "حرف"
    assert parse_pos_label("اسم الجلالة") == {
        "pos": "اسم",
        "type": "اسم الجلالة",
        "tense": None,
        "gender": None,
        "number": None,
        "person": None,
    }


# ------------------------------------------------------------- data model
def test_to_dict_is_json_serializable():
    a = farahidi.analyze("بالمدرسة")[0]
    d = a.to_dict()
    assert set(d) == {f for f in Analysis.__dataclass_fields__}
    assert d["proclitics"] == [{"form": "بِال", "description": "حرف الجر+ال:التعريف"}]
    assert isinstance(d["inflections"], list) and d["inflections"][0]["case"] == "مجرور"
    text = json.dumps(d, ensure_ascii=False)
    assert json.loads(text) == d


def test_analysis_is_hashable_and_repr_is_compact():
    a = farahidi.analyze("عندليب")[0]
    assert hash(a) == hash(farahidi.analyze("عندليب")[0])
    r = repr(a)
    assert r.startswith("Analysis(diacritized='عَنْدَلِيب'")
    assert "tense=None" not in r and "proclitics=()" not in r


def test_token_result_root_is_none_for_particles():
    results = farahidi.analyze_text("ذهب الولد إلى المدرسة")
    by_token = {r.token: r for r in results}
    assert by_token["إلى"].root is None and by_token["إلى"].analyzed
    assert by_token["ذهب"].root == "ذهب"
    assert json.dumps(by_token["إلى"].to_dict(), ensure_ascii=False)
