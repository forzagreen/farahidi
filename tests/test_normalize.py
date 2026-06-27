"""Unit tests for the Arabic string layer (ports of ArabicStringUtil/Validator/CreatHamza)."""

from __future__ import annotations

from farahidi import normalize as N


def test_remove_all_diacritics():
    assert N.remove_all_diacritics("كَتَبَ") == "كتب"
    assert N.remove_all_diacritics("مُسْتَوَى") == "مستوى"
    assert N.remove_all_diacritics("بلا") == "بلا"


def test_remove_last_diacritics_keeps_shadda():
    assert N.remove_last_diacritics("كَتَبَ") == "كَتَب"
    assert N.remove_last_diacritics("أَنّ") == "أَنّ"  # trailing shadda kept


def test_normalize_hamza_folds_carriers():
    assert N.normalize_hamza("سأل") == "سءل"
    assert N.normalize_hamza("مؤمن") == "مءمن"
    assert N.normalize_hamza("بئر") == "بءر"


def test_replace_all_hamza_drops_carriers():
    assert N.replace_all_hamza("سأل") == "سل"


def test_type_hamza():
    assert N.type_hamza("سأل") == "أ"
    assert N.type_hamza("مؤمن") == "ؤ"
    assert N.type_hamza("كتب") == ""


def test_predicates():
    assert N.is_diacritic("َ")
    assert not N.is_diacritic("ك")
    assert N.is_solar("ت")
    assert not N.is_solar("ق")
    assert N.is_definit("N1")
    assert not N.is_definit("V1")
    assert N.is_hamza("أ")
    assert not N.is_hamza("ا")


def test_word_from_root_and_pattern():
    # فَعَلَ over root ك-ت-ب -> كَتَبَ
    assert N.word_from_root_and_pattern("كتب", "فَعَلَ") == "كَتَبَ"
    # مَفْعُول over ك-ت-ب -> مَكْتُوب
    assert N.word_from_root_and_pattern("كتب", "مَفْعُول") == "مَكْتُوب"


def test_is_diac_pattern():
    assert N.is_diac_pattern("كتب", "فعل")
    assert not N.is_diac_pattern("كتب", "فمل")  # literal م must match


def test_correct_erreur_normalizes_alef_wasla():
    assert "ٱ" not in N.correct_erreur("ٱلكتاب")
