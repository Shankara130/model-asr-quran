from __future__ import annotations

from web.services.evaluation_service import evaluate_prediction, select_repeat_aware_prediction


def test_self_retry_uses_latest_correct_candidate() -> None:
    result = evaluate_prediction("abc", "axcabc")

    assert result["prediction_clean"] == "abc"
    assert result["similarity"] == 100.0
    assert result["self_corrections"] == [
        {
            "type": "prefix_superseded",
            "detected": "axc",
            "selected": "abc",
            "note": "Bacaan awal diabaikan karena ada pengulangan yang lebih cocok.",
        }
    ]


def test_plain_prediction_has_no_self_corrections() -> None:
    result = evaluate_prediction("abc", "abc")

    assert result["prediction_clean"] == "abc"
    assert result["self_corrections"] == []


def test_equal_candidates_prefer_latest_attempt() -> None:
    result = evaluate_prediction("abc", "abcabc")

    assert result["prediction_clean"] == "abc"
    assert result["self_corrections"][0]["detected"] == "abc"


def test_global_selector_does_not_trim_suffix_without_retry_prefix() -> None:
    selected, corrections = select_repeat_aware_prediction("abc", "abcdxxx")

    assert selected == "abcdxxx"
    assert corrections == []


def test_inline_self_retry_uses_newer_phrase_attempt() -> None:
    target = "ءِننننَ لمُتتَقِينَ فِي جَننننَااتِوووَعُيُون"
    prediction = "ءِننننَلمُتتَقِينَفِيجَننننَتِلوَحجَننننَتِوووَءَيُون"

    result = evaluate_prediction(target, prediction)

    assert result["similarity"] > 85
    assert result["prediction_clean"] == "ءِننننَلمُتتَقِينَفِيجَننننَتِوووَءَيُون"
    assert result["word_results"][3]["detected"] == "جَننننَتِوووَءَيُون"
    assert result["word_results"][3]["similarity"] > 75
    assert result["self_corrections"][-1]["type"] == "inline_superseded"
    assert result["self_corrections"][-1]["detected"] == "جَننننَتِلوَح"


def test_short_prefix_is_not_dropped_when_middle_phrase_repeats() -> None:
    target = "وَقَااتِلُو فِي سَبِيلِ للَااهِ وَعلَمُو ءَننننَ للَااهَ سَمِيعُن عَلِيم"
    prediction = (
        "وَقَااتِلُوفِيسَبِيلِللَااهِوَعلَمُو"
        "وَعلَمُوحَننننَللَااهَسَمِيعُنعَلِيم"
    )

    result = evaluate_prediction(target, prediction)

    assert result["similarity"] > 95
    assert result["prediction_clean"].startswith("وَقَااتِلُو")
    assert result["word_results"][0]["detected"] == "وَقَااتِلُو"
    assert result["word_results"][0]["similarity"] == 100.0
    assert result["word_results"][5]["detected"] == "حَننننَ"
    assert result["self_corrections"] == [
        {
            "type": "inline_superseded",
            "detected": "وَعلَمُو",
            "selected": "وَقَااتِلُوفِيسَبِيلِللَااهِوَعلَمُوحَننننَللَااهَسَمِيعُنعَلِيم",
            "note": (
                "Bagian pengulangan awal diabaikan karena bacaan setelahnya "
                "lebih cocok dengan target."
            ),
        }
    ]


def test_later_middle_word_retry_can_replace_closer_old_attempt() -> None:
    target = "وَءِذَ لكَوَااكِبُ ںںںتَثَرَت"
    prediction = "وَءِذَلكَوَااتِبُںںںتَثَرَتقَوَااكِبُںںںتَفَرَت"

    result = evaluate_prediction(target, prediction)

    assert result["word_results"][1]["detected"] == "قَوَااكِبُ"
    assert result["word_results"][1]["detected"] != "لكَوَااتِبُ"
    assert result["word_results"][2]["detected"] == "ںںںتَفَرَت"
    assert result["self_corrections"] == [
        {
            "type": "inline_superseded",
            "detected": "لكَوَااتِبُںںںتَثَرَت",
            "selected": "وَءِذَقَوَااكِبُںںںتَفَرَت",
            "note": (
                "Bagian pengulangan awal diabaikan karena bacaan setelahnya "
                "lebih cocok dengan target."
            ),
        }
    ]
