from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.db import get_db
from api.db.models import EvaluationResult, PracticeItem, PracticeSession
from api.schemas.home import (
    ContinuePractice,
    DailyQira,
    Greeting,
    HomeResponse,
    Recommendation,
    WeeklySnapshot,
)
from api.security import CurrentUser
from api.security.deps import require_auth

router = APIRouter(prefix="/home", tags=["home"])


async def _pick_daily_item(db: AsyncSession) -> PracticeItem:
    daily = list(
        (
            await db.execute(
                select(PracticeItem)
                .where(PracticeItem.is_daily.is_(True))
                .order_by(PracticeItem.surah_number, PracticeItem.ayah_number_start)
            )
        )
        .scalars()
        .all()
    )
    if not daily:
        item = await db.scalar(select(PracticeItem).order_by(PracticeItem.id).limit(1))
        if item is None:
            from api.core.errors import ApiError

            raise ApiError("practice_not_found")
        return item
    day_index = datetime.now(timezone.utc).timetuple().tm_yday
    return daily[day_index % len(daily)]


async def _weekly_snapshot(db: AsyncSession, user_id: str) -> WeeklySnapshot:
    week_start = datetime.now(timezone.utc) - timedelta(days=7)
    done = (
        await db.scalar(
            select(func.count())
            .select_from(PracticeSession)
            .where(
                PracticeSession.user_id == user_id,
                PracticeSession.created_at >= week_start,
                PracticeSession.status == "completed",
            )
        )
        or 0
    )
    avg = await db.scalar(
        select(func.avg(EvaluationResult.match_score))
        .join(PracticeSession, PracticeSession.id == EvaluationResult.session_id)
        .where(
            PracticeSession.user_id == user_id,
            EvaluationResult.created_at >= week_start,
            EvaluationResult.status == "completed",
        )
    )
    return WeeklySnapshot(
        sessions_done=int(done),
        sessions_target=7,
        average_match=int(avg) if avg is not None else 0,
    )


@router.get("", response_model=HomeResponse, summary="Get home summary")
async def get_home(
    principal: CurrentUser = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
) -> HomeResponse:
    """Daily Qira, greeting, weekly snapshot, last session, and a recommendation."""
    item = await _pick_daily_item(db)
    snapshot = await _weekly_snapshot(db, principal.user_id)

    last = await db.scalar(
        select(PracticeSession)
        .where(PracticeSession.user_id == principal.user_id)
        .order_by(PracticeSession.created_at.desc())
        .limit(1)
    )
    last_item = await db.get(PracticeItem, last.practice_item_id) if last else None
    last_score = None
    if last is not None:
        last_score = await db.scalar(
            select(EvaluationResult.match_score)
            .where(EvaluationResult.session_id == last.id, EvaluationResult.status == "completed")
            .order_by(EvaluationResult.created_at.desc())
            .limit(1)
        )

    greeting_message = (
        f"AI menemukan progresmu naik pelan-pelan. Fokus hari ini {item.focus or 'latihan'}."
    )
    reason = f"Kami menyarankan latihan ini untuk memperkuat pengucapan {item.focus or 'bacaan'}."

    return HomeResponse(
        daily_qira=DailyQira(
            id=f"daily_{item.id}",
            practice_item_id=item.id,
            surah_name=item.surah_name,
            ayah_label=item.ayah_label,
            arabic_text=item.arabic_text,
            translation=item.translation,
            reciter="Syaikh Al-Husary",
            estimated_minutes=item.estimated_minutes,
            focus=item.focus or None,
        ),
        greeting=Greeting(
            headline=f"Assalamualaikum, {principal.name.split()[0] if principal.name else ''}.",
            message=greeting_message,
        ),
        weekly_snapshot=snapshot,
        continue_practice=ContinuePractice(
            practice_id=last_item.id if last_item else item.id,
            surah_name=last_item.surah_name if last_item else item.surah_name,
            ayah_label=last_item.ayah_label if last_item else item.ayah_label,
            last_match=int(last_score) if last_score is not None else None,
        ),
        recommendation=Recommendation(
            practice_id=item.id,
            title=f"Latih Surah {item.surah_name}",
            reason=reason,
        ),
    )
