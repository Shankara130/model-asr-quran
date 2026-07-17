from __future__ import annotations

import asyncio
from datetime import timezone

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.core.errors import ApiError
from api.db import get_db
from api.db.models import (
    AyahHighlight,
    EvaluationResult,
    LetterInsight,
    PracticeSession,
    PracticeSessionEvent,
)
from api.schemas.evaluate import (
    EvaluateEvaluation,
    EvaluateRequest,
    EvaluateResponse,
    EvaluationHighlightOut,
    EvaluationResultOut,
    EvaluationResultResponse,
    LetterInsightOut,
    SelfCorrectionOut,
)
from api.security import CurrentUser
from api.security.deps import require_auth, require_session_owner
from api.services.evaluation_pipeline import create_evaluation, run_evaluation

router = APIRouter(prefix="/practice-sessions", tags=["evaluation"])
results_router = APIRouter(prefix="/evaluation-results", tags=["evaluation"])


@router.post(
    "/{session_id}/evaluate",
    response_model=EvaluateResponse,
    status_code=201,
    summary="Request a recitation evaluation",
)
async def evaluate(
    body: EvaluateRequest,
    session: PracticeSession = Depends(require_session_owner),
) -> EvaluateResponse:
    """Queue an evaluation of the session's uploaded audio and return the `resultId`.

    Processing is asynchronous: progress + completion are pushed over the WebSocket
    (`evaluation.queued` → `evaluation.processing` → `evaluation.completed`/`failed`).
    Fetch the result with `GET /v1/evaluation-results/{resultId}`. The outcome is an
    **initial assessment** (`evaluasi awal`), not a final ruling.
    """
    result_id, item_info, audio_url, user_id = await create_evaluation(session.id, body.audio_id)
    asyncio.create_task(run_evaluation(result_id, session.id, item_info, audio_url, user_id))
    return EvaluateResponse(
        evaluation=EvaluateEvaluation(
            result_id=result_id,
            session_id=session.id,
            status="queued",
        )
    )


@router.post(
    "/{session_id}/evaluate/retry",
    response_model=EvaluateResponse,
    status_code=201,
    summary="Retry the evaluation",
)
async def evaluate_retry(
    body: EvaluateRequest,
    session: PracticeSession = Depends(require_session_owner),
) -> EvaluateResponse:
    """Create a fresh evaluation result for the session (same async flow as evaluate)."""
    result_id, item_info, audio_url, user_id = await create_evaluation(session.id, body.audio_id)
    asyncio.create_task(run_evaluation(result_id, session.id, item_info, audio_url, user_id))
    return EvaluateResponse(
        evaluation=EvaluateEvaluation(
            result_id=result_id,
            session_id=session.id,
            status="queued",
        )
    )


async def _load_owned_result(
    result_id: str, principal: CurrentUser, db: AsyncSession
) -> EvaluationResult:
    result = await db.get(EvaluationResult, result_id)
    if result is None:
        raise ApiError("session_not_found")
    session = await db.get(PracticeSession, result.session_id)
    if session is None or session.user_id != principal.user_id:
        raise ApiError("session_not_found")
    return result


@results_router.get(
    "/{result_id}", response_model=EvaluationResultResponse, summary="Get an evaluation result"
)
async def get_result(
    result_id: str,
    principal: CurrentUser = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
) -> EvaluationResultResponse:
    """The full evaluation: match score, confidence, summary, recommendation,
    per-word highlights, and per-letter insights. `status` is `completed` or `failed`."""
    result = await _load_owned_result(result_id, principal, db)

    highlights = [
        EvaluationHighlightOut(
            segment=h.segment,
            status=h.status,
            note=h.note,
            start_index=h.start_index,
            end_index=h.end_index,
        )
        for h in (
            await db.execute(
                select(AyahHighlight)
                .where(AyahHighlight.evaluation_result_id == result_id)
                .order_by(AyahHighlight.start_index)
            )
        ).scalars()
    ]
    letter_insights = [
        LetterInsightOut(
            letter=li.letter,
            mastery_score=li.mastery_score,
            mistake_count=li.mistake_count,
        )
        for li in (
            await db.execute(
                select(LetterInsight)
                .where(LetterInsight.evaluation_result_id == result_id)
                .order_by(LetterInsight.mistake_count.desc())
            )
        ).scalars()
    ]
    session_results = list(
        (
            await db.execute(
                select(EvaluationResult)
                .where(EvaluationResult.session_id == result.session_id)
                .order_by(EvaluationResult.created_at, EvaluationResult.id)
            )
        ).scalars()
    )
    result_ids = [row.id for row in session_results]
    attempt_number = result_ids.index(result.id) + 1 if result.id in result_ids else 1
    is_latest = bool(result_ids and result.id == result_ids[-1])

    correction_events = list(
        (
            await db.execute(
                select(PracticeSessionEvent)
                .where(
                    PracticeSessionEvent.session_id == result.session_id,
                    PracticeSessionEvent.event_type == "evaluation.self_corrections",
                )
                .order_by(PracticeSessionEvent.created_at.desc())
            )
        ).scalars()
    )
    correction_event = next(
        (event for event in correction_events if event.payload.get("result_id") == result.id),
        None,
    )
    self_corrections = []
    if correction_event is not None:
        self_corrections = [
            SelfCorrectionOut(
                type=item.get("type", ""),
                detected=item.get("detected", ""),
                selected=item.get("selected", ""),
                note=item.get("note", ""),
            )
            for item in correction_event.payload.get("self_corrections", [])
            if isinstance(item, dict)
        ]

    return EvaluationResultResponse(
        result=EvaluationResultOut(
            result_id=result.id,
            session_id=result.session_id,
            practice_item_id=result.practice_item_id,
            attempt_number=attempt_number,
            is_latest=is_latest,
            match_score=result.match_score,
            confidence_level=result.confidence_level,
            summary=result.summary,
            recommendation=result.recommendation,
            highlights=highlights,
            letter_insights=letter_insights,
            self_corrections=self_corrections,
            created_at=result.created_at.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            status=result.status,
        )
    )
