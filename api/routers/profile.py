from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.db import get_db
from api.db.models import EvaluationResult, LetterMastery, PracticeSession, User, UserPreference
from api.schemas.profile import (
    Preferences,
    PreferencesRequest,
    PreferencesResponse,
    ProfileIdentityRequest,
    ProfileIdentityResponse,
    ProfileResponse,
    ProfileSummary,
    ProfileUser,
)
from api.security import CurrentUser
from api.security.deps import require_auth

router = APIRouter(prefix="/profile", tags=["profile"])


def _iso(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


async def _profile_summary(db: AsyncSession, user_id: str) -> ProfileSummary:
    total = (
        await db.scalar(
            select(func.count())
            .select_from(PracticeSession)
            .where(PracticeSession.user_id == user_id)
        )
        or 0
    )

    avg = await db.scalar(
        select(func.avg(EvaluationResult.match_score))
        .join(PracticeSession, PracticeSession.id == EvaluationResult.session_id)
        .where(
            PracticeSession.user_id == user_id,
            EvaluationResult.status == "completed",
        )
    )
    average_score = int(avg) if avg is not None else 0

    focus = await db.scalar(
        select(LetterMastery)
        .where(LetterMastery.user_id == user_id)
        .order_by(LetterMastery.score.asc())
        .limit(1)
    )

    # Naive streak: count distinct calendar days with a session, consecutive from today.
    dates = [
        row[0]
        for row in (
            await db.execute(
                select(PracticeSession.created_at)
                .where(PracticeSession.user_id == user_id)
                .order_by(PracticeSession.created_at.desc())
            )
        ).all()
    ]
    streak = 0
    seen: set[str] = set()
    cursor_day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    for iso in dates:
        day = iso[:10]
        if day in seen:
            continue
        if day == cursor_day:
            seen.add(day)
            streak += 1
            from datetime import timedelta  # local import

            cursor_day = (datetime.now(timezone.utc) - timedelta(days=streak)).strftime("%Y-%m-%d")
        elif streak == 0:
            break  # no activity today -> no active streak

    summary = ProfileSummary(
        total_sessions=int(total),
        average_score=average_score,
        focus_letter=focus.letter if focus else None,
        streak_days=streak,
    )
    summary.learning_summary = _summary_text(summary)
    summary.achievement = (
        f"Menyelesaikan {total} sesi latihan dengan rata-rata kecocokan {average_score}%."
        if total
        else None
    )
    return summary


def _summary_text(summary: ProfileSummary) -> str:
    if summary.average_score >= 80:
        base = "AI menemukan latihanmu cukup stabil."
    elif summary.average_score > 0:
        base = "AI menemukan progres yang masih bisa ditingkatkan."
    else:
        base = "Mulai latihan harianmu untuk mendapatkan ringkasan belajar."
    if summary.focus_letter:
        base += f" Huruf fokus: {summary.focus_letter}."
    return base


def _prefs_from_row(pref: UserPreference) -> Preferences:
    return Preferences(
        practice_level=pref.practice_level,
        practice_mode=pref.practice_mode,
        audio_feedback_enabled=bool(pref.audio_feedback_enabled),
        daily_report_frequency=pref.daily_report_frequency,
        reminder_enabled=bool(pref.reminder_enabled),
        reminder_time=pref.reminder_time,
    )


@router.get("", response_model=ProfileResponse, summary="Get profile, summary, and preferences")
async def get_profile(
    principal: CurrentUser = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
) -> ProfileResponse:
    """Return the user's identity, learning summary (totals, streak, focus letter),
    and preferences."""
    user = await db.get(User, principal.user_id)
    pref = await db.get(UserPreference, principal.user_id)
    if pref is None:
        pref = UserPreference(user_id=principal.user_id)
        db.add(pref)
        await db.commit()

    return ProfileResponse(
        user=ProfileUser(
            id=user.id,
            name=user.name,
            email=user.email,
            avatar_url=user.avatar_url,
            learning_level=user.learning_level,
        ),
        summary=await _profile_summary(db, principal.user_id),
        preferences=_prefs_from_row(pref),
    )


@router.patch("", response_model=ProfileIdentityResponse, summary="Update profile identity")
async def update_profile(
    body: ProfileIdentityRequest,
    principal: CurrentUser = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
) -> ProfileIdentityResponse:
    """Update name, learning level, and/or avatar URL (only provided fields change)."""
    user = await db.get(User, principal.user_id)
    if body.name is not None:
        user.name = body.name
    if body.learning_level is not None:
        user.learning_level = body.learning_level
    if body.avatar_url is not None:
        user.avatar_url = body.avatar_url
    user.updated_at = _iso(datetime.now(timezone.utc))
    await db.commit()
    return ProfileIdentityResponse(
        user=ProfileUser(
            id=user.id,
            name=user.name,
            email=user.email,
            avatar_url=user.avatar_url,
            learning_level=user.learning_level,
        )
    )


@router.patch("/preferences", response_model=PreferencesResponse, summary="Update preferences")
async def update_preferences(
    body: PreferencesRequest,
    principal: CurrentUser = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
) -> PreferencesResponse:
    """Update practice level/mode, audio feedback, report frequency, and reminders."""
    pref = await db.get(UserPreference, principal.user_id)
    if pref is None:
        pref = UserPreference(user_id=principal.user_id)
        db.add(pref)
    for field in (
        "practice_level",
        "practice_mode",
        "audio_feedback_enabled",
        "daily_report_frequency",
        "reminder_enabled",
        "reminder_time",
    ):
        value = getattr(body, field)
        if value is not None:
            setattr(pref, field, value)
    pref.updated_at = _iso(datetime.now(timezone.utc))
    await db.commit()
    return PreferencesResponse(preferences=_prefs_from_row(pref))
