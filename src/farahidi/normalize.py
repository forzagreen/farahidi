"""Arabic string utilities — a faithful port of AlKhalil's text layer.

Ports ``util/ArabicString``, ``util/ArabicStringUtil``, ``util/Validator`` and
``util/CreatHamza``. These pure string operations must match AlKhalil exactly,
because lexicon keys are produced by the same normalization — any divergence
silently drops analyses. Arabic letters and diacritics are all in the BMP, so
Python ``str`` indexing matches Java ``char`` indexing one-to-one.
"""

from __future__ import annotations

import re

# --- ArabicString constants ----------------------------------------------
ALL_ARABIC = "ٱءآأإؤئابةتثجحخدذرزسشصضطظعغفقكلمنهويى"
ALL_DIACRITICS = "ًٌٍَُِّْ"
DIACRITICS_EXCEPT_SHADDA = "ًٌٍَُِْ"

_ALL_DIACRITICS_RE = re.compile("[" + ALL_DIACRITICS + "]")
_LAST_DIAC_RE = re.compile("[" + DIACRITICS_EXCEPT_SHADDA + "]$")
_ALL_HAMZA_RE = re.compile("[أإؤئ]")
_HAMZA_TO_BARE = re.compile("[ؤأإئ]")

_DIACRITICS_SET = set(ALL_DIACRITICS)
_HAMZA_SET = set("ءأإؤئ")
_SOLAR = set("تثدذرزسشصضطظلن")
_DEFINIT_CLASSES = {"N1", "N2", "N3", "N5"}


# --- Validator predicates -------------------------------------------------
def is_diacritic(c: str) -> bool:
    return c in _DIACRITICS_SET


def is_hamza(c: str) -> bool:
    return c in _HAMZA_SET


def is_solar(c: str) -> bool:
    return c in _SOLAR


def is_definit(proc_class: str) -> bool:
    return proc_class in _DEFINIT_CLASSES


def is_numeric(c: str) -> bool:
    return c.isdigit() and c in "0123456789"


# --- ArabicStringUtil -----------------------------------------------------
def get_is_hamza(c: str) -> str:
    """``getIsHamza`` — fold a hamza-carrier to bare hamza ``ء``."""
    return "ء" if c in "أؤإئ" else c


def remove_all_diacritics(word: str) -> str:
    return _ALL_DIACRITICS_RE.sub("", word)


def remove_last_diacritics(word: str) -> str:
    return _LAST_DIAC_RE.sub("", word)


def replace_all_hamza(word: str) -> str:
    return _ALL_HAMZA_RE.sub("", word)


def normalize_hamza(word: str) -> str:
    """``getNormalizeHamza`` — map every hamza-carrier to bare ``ء``."""
    return _HAMZA_TO_BARE.sub("ء", word)


def word_contains_hamza(word: str) -> bool:
    return _ALL_HAMZA_RE.search(word) is not None


def type_hamza(word: str) -> str:
    """``getTypeHamzaFromWord`` — first hamza-carrier in the word, or ""."""
    if word_contains_hamza(word):
        for c in word:
            if c in "أؤإئ":
                return c
    return ""


def correct_erreur(word: str) -> str:
    """``correctErreur`` — normalization applied to the input before analysis."""
    if len(word) >= 3 and word[1] == "ّ":
        word = word[0] + word[2:]
    word = word.replace("ٱ", "ا")
    word = word.replace("اُ", "ا")
    word = word.replace("اَّ", "َّا")
    word = re.sub("ىً$", "ًى", word)
    word = re.sub("اً$", "ًا", word)
    word = word.replace("اَ", "ا")
    word = word.replace("اِ", "ا")
    word = word.replace("ِا", "ا")
    word = word.replace("آَ", "آ")
    return word


def get_diacritization_stem(pattern: str, stem: str) -> str:
    result = []
    j = 0
    for ch in pattern:
        if is_diacritic(ch):
            result.append(ch)
        else:
            result.append(stem[j])
            j += 1
    return "".join(result)


def add_diac_before_string(enc_voweled: str, result: str) -> str:
    head = enc_voweled[0]
    if head == "و":
        return result[:-1] + "ُ" + enc_voweled
    if head == "ي":
        return result[:-1] + "ِ" + enc_voweled
    if head == "ا":
        return result[:-1] + "َ" + enc_voweled
    return result + enc_voweled


def word_from_root_and_pattern(root: str, diac_lemma: str) -> str:
    """``getWordFromRootAndPattern`` — fill ف/ع/ل slots of a pattern with root radicals."""
    out: list[str] = []
    passe = False
    passe2 = False
    for ch in diac_lemma:
        if ch == "ف":
            out.append(root[0])
        elif ch == "ع":
            out.append(root[1])
        elif ch == "ل":
            if not passe:
                out.append(root[2])
            elif not passe2:
                out.append(root[3])
                if len(root) > 4:
                    passe2 = True
            else:
                out.append(root[4])
            if len(root) != 3:
                passe = True
        else:
            out.append(ch)
    return correct_hamza("".join(out))


def is_diac_pattern(stem: str, diac: str) -> bool:
    """``Validator.isDiacPattern`` — does the unvoweled pattern fit the stem?"""
    i = 0
    while i < len(diac) and i < len(stem):
        d = diac[i]
        if d not in ("ف", "ع", "ل") and d != stem[i]:
            return False
        i += 1
    return True


def not_compatible(normalized_word: str, voweled_word: str, segment=None, is_tool: bool = False) -> bool:
    """``Validator.notCompatible`` — true if the voweled form is inconsistent
    with the input's own (partial) diacritics. The 2-arg form (segment=None)
    matches the toolword overload; the 4-arg form folds hamza carriers."""
    use_hamza = segment is not None or is_tool
    nor = normalized_word
    vow = voweled_word
    if segment is not None or is_tool:
        enc_unv = "" if segment is None else segment.enclitic.unvoweledform
        if (
            (enc_unv != "" or is_tool or nor[-1] == "ِ")
            and vow[-1] == "ْ"
            and is_diacritic(nor[-1])
        ):
            nor = nor[:-1]
            vow = vow[:-1]
    unor = remove_all_diacritics(nor)
    uvow = remove_all_diacritics(vow)
    if vow.endswith("َا") and nor.endswith("اً"):
        return True
    if len(unor) != len(uvow):
        return True
    in_i = 0
    iv = 0
    while in_i < len(nor) and iv < len(vow):
        nc = nor[in_i]
        vc = vow[iv]
        same = nc == vc or (nc == "ا" and vc == "ى")
        if use_hamza and not same:
            same = get_is_hamza(nc) == get_is_hamza(vc)
        if same:
            in_i += 1
            iv += 1
            continue
        if not is_diacritic(nc) and not is_diacritic(vc):
            return True
        if not is_diacritic(nc) and is_diacritic(vc):
            iv += 1
            continue
        if is_diacritic(nc):
            return True
    return False


# --- CreatHamza -----------------------------------------------------------
def _is_no_relatif(c: str) -> bool:
    return c not in ("د", "ذ", "ر", "ز", "و")


def _start_hamza(word: str) -> str:
    if len(word) > 1 and word[0] == "ء":
        first = "إ" if word[1] == "ِ" else "أ"
    else:
        first = word[0]
    word_f = first + word[1:]
    if word_f.startswith("أَا"):
        word_f = "آ" + word_f[3:]
    return word_f


def _end_hamza(word: str, pos: int, length: int) -> str:
    if pos > 1 and word[pos - 1] == "ِ":
        return "ئ"
    if pos > 1 and word[pos - 1] == "َ":
        return "أ"
    if pos > 3 and word[pos - 1] == "ُ" and word[pos - 2] == "ّ" and word[pos - 3] == "و":
        return "ء"
    if pos > 1 and word[pos - 1] == "ُ":
        return "ؤ"
    return "ء"


def _is_nibra_hamza(word: str, pos: int, length: int) -> bool:
    if pos > 0 and word[pos - 1] == "ِ":
        return True
    if (pos > 0 and word[pos - 1] == "ي") or (
        pos > 1 and word[pos - 1] == "ْ" and word[pos - 2] == "ي"
    ):
        return True
    if (
        pos > 1
        and word[pos - 1] == "ْ"
        and _is_no_relatif(word[pos - 2])
        and pos + 2 < length
        and (word[pos + 1] == "َ" or word[pos + 1] == "ً")
        and word[pos + 2] == "ا"
    ):
        return True
    if (
        pos > 0
        and word[pos - 1] in ("ا", "ي", "و")
        and (
            (pos + 1 < length and word[pos + 1] == "ِ")
            or (pos + 2 < length and word[pos + 2] == "ِ" and word[pos + 1] == "ّ")
        )
    ):
        return True
    return (
        pos > 0
        and word[pos - 1] in ("ْ", "َ", "ُ")
        and (
            (pos + 1 < length and word[pos + 1] == "ِ")
            or (pos + 2 < length and word[pos + 2] == "ِ" and word[pos + 1] == "ّ")
        )
    )


def _is_waw_hamza(word: str, pos: int, length: int) -> bool:
    if pos > 0 and word[pos - 1] in ("ا", "ْ") and word[pos - 1] != "ي" and word[pos - 1] != "و":
        if pos + 1 < length and word[pos + 1] == "ُ":
            return pos + 2 < length
        if pos + 2 < length and word[pos + 2] == "ُ" and word[pos + 1] == "ّ":
            return (word[pos + 3] != "و") if pos + 3 < length else False
    if pos > 0 and word[pos - 1] == "َ" and (
        (pos + 1 < length and word[pos + 1] == "ُ")
        or (pos + 2 < length and word[pos + 2] == "ُ" and word[pos + 1] == "ّ")
    ):
        return True
    if pos > 0 and word[pos - 1] == "ُ" and (
        (pos + 1 < length and word[pos + 1] != "ِ")
        or (pos + 2 < length and word[pos + 2] != "ِ" and word[pos + 1] == "ّ")
    ):
        return pos <= 2 or word[pos - 2] != "ّ" or word[pos - 3] != "و"
    return False


def _is_alif_hamza(word: str, pos: int, length: int) -> bool:
    if pos > 0 and word[pos - 1] == "َ" and (
        (pos + 1 < length and word[pos + 1] == "ْ")
        or (pos + 1 < length and word[pos + 1] == "َ")
        or (pos + 2 < length and word[pos + 2] == "َ" and word[pos + 1] == "ّ")
    ):
        return True
    if pos > 1 and word[pos - 1] == "ْ" and word[pos - 2] == "و" and pos + 1 < length and word[pos + 1] == "َ":
        return False
    if pos > 0 and word[pos - 1] == "ْ":
        if pos + 2 < length and word[pos + 1] == "ً" and word[pos + 2] == "ا":
            return False
        if (
            pos + 4 < length
            and word[pos + 1] == "َ"
            and word[pos + 2] == "ا"
            and word[pos + 3] == "ن"
            and word[pos + 4] == "ِ"
        ):
            return False
        if (pos + 1 < length and word[pos + 1] == "َ") or (
            pos + 2 < length and word[pos + 1] == "ّ" and word[pos + 2] == "َ"
        ):
            return True
    return False


def correct_hamza(word: str) -> str:
    """``CreatHamza.correctHamza`` — re-attach hamza to its correct carrier."""
    word = _HAMZA_TO_BARE.sub("ء", word)
    word = _start_hamza(word)
    wrd_d = remove_all_diacritics(word)
    length = len(word)
    if word.startswith("اءْ"):
        word = "ائْ" + word[3:]
        length = len(word)
    out: list[str] = []
    ip = 0
    i = 0
    while i < length:
        c = word[i]
        if c == "ء":
            if ip + 1 == len(wrd_d):
                out.append(_end_hamza(word, i, length))
            elif _is_nibra_hamza(word, i, length):
                out.append("ئ")
            elif _is_waw_hamza(word, i, length):
                out.append("ؤ")
            elif _is_alif_hamza(word, i, length):
                if i + 2 < length and word[i + 1] == "َ" and word[i + 2] == "ا":
                    out.append("آ")
                    i += 2
                elif (
                    i + 3 < length
                    and word[i + 1] == "ّ"
                    and word[i + 2] == "َ"
                    and word[i + 3] == "ا"
                ):
                    out.append("آَّ")
                    i += 3
                elif (
                    i + 3 < length
                    and word[i + 1] == "َ"
                    and word[i + 2] == "ء"
                    and word[i + 3] == "ْ"
                ):
                    out.append("آ")
                    i += 3
                else:
                    out.append("أ")
            else:
                out.append(c)
        else:
            out.append(c)
        if not is_diacritic(word[i]):
            ip += 1
        i += 1
    return "".join(out)


def correct_stem_hamza(s: str) -> str:
    """``CreatHamza.correctStemHamza``."""
    length = len(s)
    out: list[str] = []
    i = 0
    while i < length:
        c = s[i]
        if c in ("ء", "أ"):
            if i + 1 < length and s[i + 1] == "ا":
                if i - 1 >= 0 and s[i - 1] == "ا":
                    out.append(c)
                else:
                    out.append("آ")
                    i += 1
            else:
                out.append(c)
        else:
            out.append(c)
        i += 1
    return "".join(out)
