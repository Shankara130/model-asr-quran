from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.db.models import EvaluationResult, LetterInsight, LetterMastery, PracticeSession
from api.schemas.insights import LetterMasteryItem, WeeklyInsight, WeeklyLetterMastery


def default_week_start() -> str:
    today = datetime.now(timezone.utc).date()
    monday = today - timedelta(days=today.weekday())
    return monday.strftime("%Y-%m-%d")


def _week_bounds(week_start: str) -> tuple[str, str]:
    start = datetime.strptime(week_start, "%Y-%m-%d").date()
    end = start + timedelta(days=7)
    return f"{start}T00:00:00Z", f"{end}T00:00:00Z"


async def _results_in_range(
    db: AsyncSession, user_id: str, start_iso: str, end_iso: str
) -> list[EvaluationResult]:
    return list(
        (
            await db.execute(
                select(EvaluationResult)
                .join(PracticeSession, PracticeSession.id == EvaluationResult.session_id)
                .where(
                    PracticeSession.user_id == user_id,
                    EvaluationResult.status == "completed",
                    EvaluationResult.created_at >= start_iso,
                    EvaluationResult.created_at < end_iso,
                )
                .order_by(EvaluationResult.created_at)
            )
        ).scalars()
    )


async def build_weekly(db: AsyncSession, user_id: str, week_start: str) -> WeeklyInsight:
    start_iso, end_iso = _week_bounds(week_start)
    prev_start = (datetime.strptime(week_start, "%Y-%m-%d") - timedelta(days=7)).strftime(
        "%Y-%m-%dT00:00:00Z"
    )
    prev_end = start_iso

    results = await _results_in_range(db, user_id, start_iso, end_iso)
    prev_results = await _results_in_range(db, user_id, prev_start, prev_end)

    scores = [r.match_score for r in results]
    prev_scores = [r.match_score for r in prev_results]
    average_score = int(round(sum(scores) / len(scores))) if scores else 0
    prev_avg = int(round(sum(prev_scores) / len(prev_scores))) if prev_scores else 0
    growth = average_score - prev_avg

    # Daily trend for the 7 days of the week.
    by_day: dict[str, list[int]] = {}
    for r in results:
        by_day.setdefault(r.created_at[:10], []).append(r.match_score)
    start_date = datetime.strptime(week_start, "%Y-%m-%d").date()
    trend = []
    for i in range(7):
        day = (start_date + timedelta(days=i)).strftime("%Y-%m-%d")
        day_scores = by_day.get(day)
        trend.append(int(round(sum(day_scores) / len(day_scores))) if day_scores else 0)

    # Letter mastery this week from per-result letter insights.
    result_ids = [r.id for r in results]
    weekly_letters = await _letter_insights_for(db, result_ids)
    focus_letter = None
    if weekly_letters:
        focus_letter = min(weekly_letters, key=lambda x: x.score).letter

    practice_count = len({r.session_id for r in results})

    if scores:
        summary = (
            f"AI menemukan performa {'meningkat' if growth >= 0 else 'menurun'} minggu ini"
            + (f", namun huruf {focus_letter} masih sering perlu dicek." if focus_letter else ".")
        )
    else:
        summary = "Belum ada latihan minggu ini. Mulai Daily Qira untuk melihat insight."

    suggestion = (
        f"Latih huruf {focus_letter} 5 menit dan ulangi frasa dengan tempo pelan."
        if focus_letter
        else "Lakukan latihan harian singkat untuk membangun kebiasaan."
    )

    return WeeklyInsight(
        practice_count=practice_count,
        average_score=average_score,
        growth_percent=growth,
        focus_letter=focus_letter,
        summary=summary,
        trend=trend,
        letter_mastery=[
            WeeklyLetterMastery(letter=wl.letter, score=wl.score, mistake_count=wl.mistake_count)
            for wl in weekly_letters
        ],
        suggestion=suggestion,
    )


async def _letter_insights_for(db: AsyncSession, result_ids: list[str]) -> list[LetterInsight]:
    if not result_ids:
        return []
    rows = list(
        (
            await db.execute(
                select(LetterInsight).where(LetterInsight.evaluation_result_id.in_(result_ids))
            )
        ).scalars()
    )
    agg: dict[str, dict] = {}
    for li in rows:
        bucket = agg.setdefault(li.letter, {"letter": li.letter, "score": [], "mistake_count": 0})
        bucket["score"].append(li.mastery_score)
        bucket["mistake_count"] += li.mistake_count

    out: list[LetterInsight] = []
    for letter, data in agg.items():
        avg_score = int(round(sum(data["score"]) / len(data["score"])))
        out.append(
            LetterInsight(
                id=letter,
                evaluation_result_id="",
                letter=letter,
                mastery_score=avg_score,
                mistake_count=data["mistake_count"],
                created_at="",
            )
        )
    out.sort(key=lambda x: (-x.mistake_count, x.letter))
    return out


async def letter_mastery_items(db: AsyncSession, user_id: str) -> list[LetterMasteryItem]:
    rows = list(
        (
            await db.execute(
                select(LetterMastery)
                .where(LetterMastery.user_id == user_id)
                .order_by(LetterMastery.mistake_count.desc())
            )
        ).scalars()
    )
    return [
        LetterMasteryItem(
            letter=r.letter,
            score=r.score,
            mistake_count=r.mistake_count,
            last_practiced_at=r.last_practiced_at,
        )
        for r in rows
    ]
