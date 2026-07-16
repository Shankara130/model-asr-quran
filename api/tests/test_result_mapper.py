from __future__ import annotations

from api.services import result_mapper


def _raw(similarity, exact, differences, word_results=None, self_corrections=None):
    return {
        "similarity": similarity,
        "exact_match": exact,
        "differences": differences,
        "tajwid_feedback": [],
        "word_results": word_results or [],
        "prediction_clean": "p",
        "self_corrections": self_corrections or [],
    }


def test_high_confidence_mapping():
    mapped = result_mapper.map_result(_raw(92.0, False, []), {"arabic_text": "ا ب"})
    assert mapped["match_score"] == 92
    assert mapped["confidence_level"] == "high"
    assert mapped["summary"]
    # highlights follow the arabic segments; absent word_results default to "read"
    assert [h["status"] for h in mapped["highlights"]] == ["read", "read"]


def test_self_corrections_passthrough():
    correction = {
        "type": "prefix_superseded",
        "detected": "axc",
        "selected": "abc",
        "note": "Bacaan awal diabaikan karena ada pengulangan yang lebih cocok.",
    }

    mapped = result_mapper.map_result(
        _raw(92.0, False, [], self_corrections=[correction]),
        {"arabic_text": "ا"},
    )

    assert mapped["self_corrections"] == [correction]


def test_low_confidence_with_letter_aggregation():
    differences = [
        {
            "type": "replace",
            "target": "ا",
            "detected": "ب",
            "target_index": 0,
            "prediction_index": 0,
        },
        {"type": "delete", "target": "ض", "detected": "", "target_index": 1, "prediction_index": 1},
        {"type": "insert", "target": "", "detected": "ن", "target_index": 2, "prediction_index": 2},
    ]
    mapped = result_mapper.map_result(_raw(20.0, False, differences), {"arabic_text": "ا ض"})
    assert mapped["match_score"] == 20
    assert mapped["confidence_level"] == "low"
    by_letter = {li["letter"]: li for li in mapped["letter_insights"]}
    assert by_letter["ا"]["mistake_count"] == 1
    assert by_letter["ض"]["mistake_count"] == 1
    assert by_letter["ن"]["mistake_count"] == 1  # insert attributes to detected
    assert all(
        li["mastery_score"] == max(0, 100 - li["mistake_count"] * 25)
        for li in mapped["letter_insights"]
    )


def test_highlight_status_thresholds():
    arabic = "ا ب ج"
    word_results = [
        {
            "similarity": 100.0,
            "exact_match": True,
            "differences": [],
            "tajwid_feedback": [],
            "detected": "ا",
        },
        {
            "similarity": 50.0,
            "exact_match": False,
            "differences": [],
            "tajwid_feedback": [],
            "detected": "x",
        },
        {
            "similarity": 20.0,
            "exact_match": False,
            "differences": [],
            "tajwid_feedback": [],
            "detected": "",
        },
    ]
    mapped = result_mapper.map_result(_raw(60.0, False, [], word_results), {"arabic_text": arabic})
    statuses = [h["status"] for h in mapped["highlights"]]
    assert statuses == ["read", "needs_check", "current"]  # last empty->current
    # char offsets align to the arabic text
    seg = mapped["highlights"][1]
    assert "ا ب ج"[seg["start_index"] : seg["end_index"]] == seg["segment"]


def test_summary_never_claims_finality():
    mapped = result_mapper.map_result(_raw(50.0, False, []), {"arabic_text": "ا"})
    assert "evaluasi awal" in mapped["summary"].lower()
