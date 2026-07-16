from __future__ import annotations

from web.services.evaluation_service import evaluate_prediction


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
