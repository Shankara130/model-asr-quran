from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from api.db import get_db
from api.schemas.insights import (
    LetterMasteryResponse,
    WeeklyInsightResponse,
)
from api.security import CurrentUser
from api.security.deps import require_auth
from api.services.insights_builder import (
    build_weekly,
    default_week_start,
    letter_mastery_items,
)

router = APIRouter(prefix="/insights", tags=["insights"])


@router.get("/weekly", response_model=WeeklyInsightResponse, summary="Weekly insight")
async def weekly_insight(
    principal: CurrentUser = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
    week_start: str = Query(
        default=None,
        alias="weekStart",
        description="Week start `YYYY-MM-DD` (defaults to this Monday).",
    ),
    timezone: str = Query(
        default="Asia/Jakarta",
        description="Accepted for API parity; week is computed in UTC for now.",
    ),
) -> WeeklyInsightResponse:
    """Practice count, average score, growth vs last week, daily trend, letter mastery,
    and a suggestion for the week."""
    week = week_start or default_week_start()
    insight = await build_weekly(db, principal.user_id, week)
    return WeeklyInsightResponse(weekly_insight=insight)


@router.get("/letter-mastery", response_model=LetterMasteryResponse, summary="Per-letter mastery")
async def letter_mastery(
    principal: CurrentUser = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
) -> LetterMasteryResponse:
    """Cumulative mastery score and mistake count per Arabic letter for the user."""
    items = await letter_mastery_items(db, principal.user_id)
    return LetterMasteryResponse(items=items)
