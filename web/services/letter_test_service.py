from __future__ import annotations

from typing import Any


LETTER_DEFINITIONS = [
    {
        "letter": "ا",
        "name": "Alif/Hamzah",
        "forms": [
            ("أَ", "ءَ", "a"),
            ("إِ", "ءِ", "i"),
            ("أُ", "ءُ", "u"),
        ],
    },
    {"letter": "ب", "name": "Ba"},
    {"letter": "ت", "name": "Ta"},
    {"letter": "ث", "name": "Tsa"},
    {"letter": "ج", "name": "Jim"},
    {"letter": "ح", "name": "Ha tenggorokan"},
    {"letter": "خ", "name": "Kha"},
    {"letter": "د", "name": "Dal"},
    {"letter": "ذ", "name": "Dzal"},
    {"letter": "ر", "name": "Ra"},
    {"letter": "ز", "name": "Zai"},
    {"letter": "س", "name": "Sin"},
    {"letter": "ش", "name": "Syin"},
    {"letter": "ص", "name": "Shad"},
    {"letter": "ض", "name": "Dhad"},
    {"letter": "ط", "name": "Tha tebal"},
    {"letter": "ظ", "name": "Zha"},
    {"letter": "ع", "name": "Ain"},
    {"letter": "غ", "name": "Ghain"},
    {"letter": "ف", "name": "Fa"},
    {"letter": "ق", "name": "Qaf"},
    {"letter": "ك", "name": "Kaf"},
    {"letter": "ل", "name": "Lam"},
    {"letter": "م", "name": "Mim"},
    {"letter": "ن", "name": "Nun"},
    {"letter": "ه", "name": "Ha ringan"},
    {"letter": "و", "name": "Wau"},
    {"letter": "ي", "name": "Ya"},
]

HARAKAT_FORMS = [
    ("َ", "a", "fathah"),
    ("ِ", "i", "kasrah"),
    ("ُ", "u", "dhammah"),
]

SIMILAR_SOUND_GROUPS = [
    {
        "letters": {"ح", "ه", "خ"},
        "warning": (
            "Hati-hati: ح, ه, dan خ memiliki "
            "makhraj yang berdekatan."
        ),
    },
    {
        "letters": {"ث", "س", "ص"},
        "warning": (
            "Hati-hati: ث, س, dan ص dapat "
            "terdengar mirip."
        ),
    },
    {
        "letters": {"ذ", "ز", "ظ"},
        "warning": (
            "Hati-hati: ذ, ز, dan ظ sering "
            "tertukar."
        ),
    },
    {
        "letters": {"ت", "ط", "د", "ض"},
        "warning": (
            "Perhatikan perbedaan bunyi tipis "
            "dan tebal."
        ),
    },
    {
        "letters": {"ع", "ء"},
        "warning": (
            "Huruf ع tidak boleh berubah "
            "menjadi hamzah."
        ),
    },
    {
        "letters": {"ق", "ك"},
        "warning": (
            "Huruf ق dibaca lebih belakang "
            "dan tebal daripada ك."
        ),
    },
    {
        "letters": {"غ", "خ"},
        "warning": (
            "Huruf غ bersuara, sedangkan خ "
            "lebih berdesis."
        ),
    },
]


def build_letter_tests() -> list[dict[str, Any]]:
    tests: list[dict[str, Any]] = []

    for definition in LETTER_DEFINITIONS:
        letter = definition["letter"]
        name = definition["name"]
        custom_forms = definition.get("forms")

        if custom_forms:
            forms = [
                {
                    "display": display,
                    "phoneme": phoneme,
                    "latin": latin,
                    "harakat": {
                        "a": "fathah",
                        "i": "kasrah",
                        "u": "dhammah",
                    }[latin],
                }
                for display, phoneme, latin
                in custom_forms
            ]
        else:
            forms = [
                {
                    "display": f"{letter}{mark}",
                    "phoneme": f"{letter}{mark}",
                    "latin": (
                        f"{name.lower()}-"
                        f"{latin_vowel}"
                    ),
                    "harakat": harakat_name,
                }
                for mark, latin_vowel, harakat_name
                in HARAKAT_FORMS
            ]

        warning = next(
            (
                group["warning"]
                for group in SIMILAR_SOUND_GROUPS
                if letter in group["letters"]
            ),
            (
                "Fokuskan pengucapan pada "
                "makhraj huruf."
            ),
        )

        for form in forms:
            tests.append({
                "index": len(tests),
                "letter": letter,
                "letter_name": name,
                "display": form["display"],
                "target_phoneme": form["phoneme"],
                "latin_hint": form["latin"],
                "harakat": form["harakat"],
                "warning": warning,
            })

    return tests


LETTER_TESTS = build_letter_tests()


def get_letter_test(
    index: int,
) -> dict[str, Any]:
    if not LETTER_TESTS:
        raise RuntimeError(
            "Daftar uji huruf kosong."
        )

    safe_index = max(
        0,
        min(index, len(LETTER_TESTS) - 1),
    )

    item = dict(LETTER_TESTS[safe_index])

    item["total"] = len(LETTER_TESTS)
    item["is_first"] = safe_index == 0
    item["is_last"] = (
        safe_index == len(LETTER_TESTS) - 1
    )

    return item