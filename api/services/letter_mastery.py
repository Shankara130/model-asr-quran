from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.core.ids import new_id
from api.db.models import LetterMastery


def _iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


async def update_for_result(
    db: AsyncSession, user_id: str, letter_insights: list[dict[str, Any]]
) -> None:
    """Rolling per-(user, letter) mastery update after a completed evaluation."""
    if not letter_insights:
        return
    now = _iso()
    for li in letter_insights:
        letter = li["letter"]
        new_score = int(li["mastery_score"])
        add_mistakes = int(li["mistake_count"])

        row = await db.scalar(
            select(LetterMastery).where(
                LetterMastery.user_id == user_id,
                LetterMastery.letter == letter,
            )
        )
        if row is None:
            db.add(
                LetterMastery(
                    id=new_id("lm"),
                    user_id=user_id,
                    letter=letter,
                    score=new_score,
                    mistake_count=add_mistakes,
                    last_practiced_at=now,
                    updated_at=now,
                )
            )
        else:
            row.score = round(0.7 * row.score + 0.3 * new_score)
            row.mistake_count = row.mistake_count + add_mistakes
            row.last_practiced_at = now
            row.updated_at = now
    await db.flush()
