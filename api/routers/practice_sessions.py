from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.core.errors import ApiError
from api.core.ids import new_session_id
from api.core.pagination import decode_cursor, encode_cursor
from api.db import get_db
from api.db.models import AudioUpload, EvaluationResult, PracticeItem, PracticeSession
from api.schemas.practice_sessions import (
    CancelSessionResponse,
    CreateSessionRequest,
    CreateSessionResponse,
    GetSessionResponse,
    RealtimeConfig,
    SessionCancelled,
    SessionCreated,
    SessionFetched,
    SessionHistoryItem,
    SessionHistoryResponse,
    UploadConfig,
)
from api.security import CurrentUser
from api.security.deps import require_auth, require_session_owner
from api.security.tokens import issue_realtime_token
from api.settings import settings

router = APIRouter(prefix="/practice-sessions", tags=["practice-sessions"])


def _iso(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def _realtime_url(request: Request, session_id: str) -> str:
    scheme = "wss" if request.url.scheme == "https" else "ws"
    return f"{scheme}://{request.url.netloc}/v1/realtime/practice-sessions/{session_id}"


@router.post(
    "", response_model=CreateSessionResponse, status_code=201, summary="Start a practice session"
)
async def create_session(
    body: CreateSessionRequest,
    request: Request,
    principal: CurrentUser = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
) -> CreateSessionResponse:
    """Create a session for a practice item and return a short-lived realtime token
    plus the chunk-upload configuration."""
    item = await db.get(PracticeItem, body.practice_item_id)
    if item is None:
        raise ApiError("practice_not_found")

    now = datetime.now(timezone.utc)
    device = body.device
    session = PracticeSession(
        id=new_session_id(),
        user_id=principal.user_id,
        practice_item_id=item.id,
        status="started",
        client_session_id=body.client_session_id,
        device_platform=device.platform if device else None,
        device_model=device.model if device else None,
        app_version=device.app_version if device else None,
        started_at=now,
    )
    db.add(session)
    await db.commit()

    return CreateSessionResponse(
        session=SessionCreated(
            id=session.id,
            practice_item_id=session.practice_item_id,
            user_id=session.user_id,
            status=session.status,
            created_at=_iso(session.created_at),
            expires_at=_iso(now + timedelta(seconds=settings.realtime_token_ttl_seconds)),
        ),
        realtime=RealtimeConfig(
            url=_realtime_url(request, session.id),
            token=issue_realtime_token(principal.user_id, session.id),
            expires_in=settings.realtime_token_ttl_seconds,
        ),
        upload=UploadConfig(
            mode="chunked",
            chunk_size_bytes=settings.chunk_size_bytes,
            accepted_mime_types=list(settings.accepted_mime_types),
            max_duration_seconds=settings.max_audio_duration_seconds,
        ),
    )


async def _latest_audio_url(db: AsyncSession, session_id: str) -> str | None:
    row = await db.scalar(
        select(AudioUpload)
        .where(AudioUpload.session_id == session_id, AudioUpload.status == "uploaded")
        .order_by(AudioUpload.completed_at.desc())
        .limit(1)
    )
    return row.audio_url if row else None


@router.get("/{session_id}", response_model=GetSessionResponse, summary="Get a session")
async def get_session(
    session: PracticeSession = Depends(require_session_owner),
    db: AsyncSession = Depends(get_db),
) -> GetSessionResponse:
    """Current status and the latest uploaded audio URL for a session."""
    return GetSessionResponse(
        session=SessionFetched(
            id=session.id,
            practice_item_id=session.practice_item_id,
            status=session.status,
            audio_url=await _latest_audio_url(db, session.id),
            created_at=_iso(session.created_at),
            completed_at=_iso(session.completed_at) if session.completed_at else None,
        )
    )


@router.post(
    "/{session_id}/cancel", response_model=CancelSessionResponse, summary="Cancel a session"
)
async def cancel_session(
    session: PracticeSession = Depends(require_session_owner),
    db: AsyncSession = Depends(get_db),
) -> CancelSessionResponse:
    """Mark a started session cancelled (`session_invalid_state` if already finished)."""
    if session.status in {"completed", "cancelled"}:
        raise ApiError("session_invalid_state")
    session.status = "cancelled"
    session.updated_at = datetime.now(timezone.utc)
    await db.commit()
    return CancelSessionResponse(session=SessionCancelled(id=session.id, status="cancelled"))


@router.get(
    "",
    response_model=SessionHistoryResponse,
    tags=["insights"],
    summary="List practice history",
)
async def list_sessions(
    principal: CurrentUser = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
    limit: int = Query(default=20, ge=1, le=100, description="Page size."),
    cursor: str | None = Query(
        default=None, description="Opaque cursor from a previous nextCursor."
    ),
    status: str | None = Query(
        default=None, description="Filter by session status (e.g. completed)."
    ),
) -> SessionHistoryResponse:
    """Cursor-paginated history joining sessions with their practice item and latest result."""
    offset = int(decode_cursor(cursor).get("o", 0))
    stmt = (
        select(PracticeSession)
        .where(PracticeSession.user_id == principal.user_id)
        .order_by(PracticeSession.created_at.desc())
    )
    if status:
        stmt = stmt.where(PracticeSession.status == status)

    page = list((await db.execute(stmt.offset(offset).limit(limit + 1))).scalars().all())
    has_more = len(page) > limit
    page = page[:limit]

    item_ids = {s.practice_item_id for s in page}
    items = {
        i.id: i
        for i in (
            await db.execute(select(PracticeItem).where(PracticeItem.id.in_(item_ids)))
        ).scalars()
    }
    session_ids = [s.id for s in page]
    results: dict[str, EvaluationResult] = {}
    if session_ids:
        rows = list(
            (
                await db.execute(
                    select(EvaluationResult).where(EvaluationResult.session_id.in_(session_ids))
                )
            ).scalars()
        )
        for r in rows:
            cur = results.get(r.session_id)
            if cur is None or r.created_at > cur.created_at:
                results[r.session_id] = r

    next_cursor = encode_cursor({"o": offset + limit}) if has_more else None
    items_out = [
        SessionHistoryItem(
            id=s.id,
            practice_item_id=s.practice_item_id,
            surah_name=items[s.practice_item_id].surah_name if s.practice_item_id in items else "",
            ayah_label=items[s.practice_item_id].ayah_label if s.practice_item_id in items else "",
            status=s.status,
            match_score=results[s.id].match_score if s.id in results else None,
            confidence_level=results[s.id].confidence_level if s.id in results else None,
            created_at=_iso(s.created_at),
            completed_at=_iso(s.completed_at) if s.completed_at else None,
        )
        for s in page
    ]
    return SessionHistoryResponse(items=items_out, next_cursor=next_cursor)
