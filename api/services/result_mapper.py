from __future__ import annotations

from collections import defaultdict
from typing import Any

from api.services.seed_data import _segments
from api.settings import settings

try:
    from quran_asr.tajwid.interpreter import ARABIC_LETTERS
except Exception:  # pragma: no cover
    ARABIC_LETTERS = set("ابتثجحخدذرزسشصضطظعغفقكلمنهويءں")


def confidence_level(score: int) -> str:
    if score >= settings.confidence_high:
        return "high"
    if score >= settings.confidence_medium:
        return "medium"
    return "low"


def _highlight_status(similarity: float, exact_match: bool, is_last: bool, detected: str) -> str:
    if exact_match or similarity >= settings.confidence_high:
        return "read"
    if is_last and (not detected or len(detected) <= 1):
        return "current"
    if similarity >= settings.confidence_medium:
        return "current"
    if similarity >= 35:
        return "needs_check"
    return "needs_retry"


def _note(status: str, segment: str, word_result: dict) -> str:
    tajwid = word_result.get("tajwid_feedback") or []
    seen: list[str] = []
    for item in tajwid:
        msg = (item.get("message") or "").strip()
        if msg and msg not in seen:
            seen.append(msg)
        if len(seen) >= 2:
            break
    if seen:
        return " ".join(seen)
    if status == "read":
        return "Terbaca baik."
    return f"Perlu dicek pada bagian {segment}."


def build_highlights(word_results: list[dict], arabic_text: str) -> list[dict]:
    segments = _segments(arabic_text)
    total = len(segments)
    highlights: list[dict] = []
    for i, seg in enumerate(segments):
        wr = word_results[i] if i < len(word_results) else {}
        similarity = float(wr.get("similarity", 100.0))
        exact = bool(wr.get("exact_match", False))
        detected = str(wr.get("detected", ""))
        status = _highlight_status(similarity, exact, i == total - 1, detected)
        highlights.append(
            {
                "segment": seg["text"],
                "status": status,
                "note": _note(status, seg["text"], wr),
                "start_index": seg["startChar"],
                "end_index": seg["endChar"],
            }
        )
    return highlights


def aggregate_letters(raw: dict) -> list[dict]:
    counts: dict[str, int] = defaultdict(int)

    def account(diff: dict) -> None:
        dtype = diff.get("type")
        target = diff.get("target") or ""
        detected = diff.get("detected") or ""
        if dtype in {"replace", "delete"} and len(target) == 1 and target in ARABIC_LETTERS:
            counts[target] += 1
        if dtype == "insert" and len(detected) == 1 and detected in ARABIC_LETTERS:
            counts[detected] += 1

    for diff in raw.get("differences") or []:
        account(diff)
    for wr in raw.get("word_results") or []:
        for diff in wr.get("differences") or []:
            account(diff)

    return [
        {"letter": letter, "mastery_score": max(0, 100 - count * 25), "mistake_count": count}
        for letter, count in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
    ]


def build_summary(confidence: str, highlights: list[dict]) -> tuple[str, str]:
    focus = sorted(
        {h["segment"] for h in highlights if h["status"] in {"needs_check", "needs_retry"}}
    )
    focus_text = ", ".join(focus) if focus else "huruf tertentu"
    level_phrase = {
        "high": "sangat stabil",
        "medium": "cukup stabil",
        "low": "masih perlu latihan",
    }[confidence]
    summary = (
        f"Evaluasi awal menunjukkan bacaan {level_phrase}. "
        f"AI menemukan bagian yang perlu dicek pada {focus_text}."
    )
    if confidence == "high":
        recommendation = "Pertahankan tempo dan dengarkan referensi untuk menjaga konsistensi."
    elif confidence == "medium":
        recommendation = (
            "Coba ulangi bagian ini dengan tempo lebih pelan dan dengarkan referensi "
            "sekali sebelum merekam."
        )
    else:
        recommendation = (
            f"Latih ulang bagian yang ditandai, fokus pada {focus_text}, lalu ulangi rekaman."
        )
    return summary, recommendation


def map_result(raw: dict, item_info: dict[str, Any]) -> dict[str, Any]:
    """Map an ``evaluate_prediction`` dict to the spec evaluation result shape."""
    similarity = float(raw.get("similarity", 0.0) or 0.0)
    match_score = int(round(max(0.0, min(100.0, similarity))))
    confidence = confidence_level(match_score)
    highlights = build_highlights(raw.get("word_results") or [], item_info.get("arabic_text", ""))
    letter_insights = aggregate_letters(raw)
    summary, recommendation = build_summary(confidence, highlights)

    return {
        "match_score": match_score,
        "confidence_level": confidence,
        "summary": summary,
        "recommendation": recommendation,
        "highlights": highlights,
        "letter_insights": letter_insights,
        "prediction": raw.get("prediction_clean", ""),
    }
