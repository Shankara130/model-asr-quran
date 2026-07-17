from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from api.core.errors import ApiError
from api.core.ids import new_audio_id, new_id, new_upload_id
from api.db import get_db
from api.db.models import AudioChunk, AudioUpload, PracticeSession
from api.schemas.audio import (
    AudioOut,
    ChunkAbortResponse,
    ChunkCompleteRequest,
    ChunkCompleteResponse,
    ChunkInitRequest,
    ChunkInitResponse,
    ChunkPartResponse,
    ChunkUploadConfig,
    SimpleUploadResponse,
)
from api.security.deps import require_session_owner
from api.services import upload_store
from api.settings import settings
from api.ws.events import audio_chunk_received, audio_uploaded
from api.ws.hub import hub

router = APIRouter(prefix="/practice-sessions", tags=["audio"])

_MIME_EXT = {
    "audio/webm": "webm",
    "audio/mp4": "mp4",
    "audio/m4a": "m4a",
    "audio/x-m4a": "m4a",
    "audio/wav": "wav",
    "audio/x-wav": "wav",
    "audio/mpeg": "mp3",
}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _ext(mime: str, fallback: str = "webm") -> str:
    return _MIME_EXT.get((mime or "").lower(), fallback)


def _audio_out(upload: AudioUpload) -> AudioOut:
    return AudioOut(
        id=upload.id,
        session_id=upload.session_id,
        audio_url=upload.audio_url,
        duration_ms=upload.duration_ms,
        mime_type=upload.mime_type,
        size_bytes=upload.size_bytes,
        status=upload.status,
    )


async def _resolve_upload(db: AsyncSession, session_id: str, upload_id: str) -> AudioUpload:
    upload = await db.scalar(
        select(AudioUpload).where(
            AudioUpload.upload_id == upload_id,
            AudioUpload.session_id == session_id,
        )
    )
    if upload is None:
        raise ApiError("audio_upload_failed", details={"uploadId": upload_id})
    return upload


@router.post(
    "/{session_id}/audio",
    response_model=SimpleUploadResponse,
    summary="Upload audio (simple multipart)",
)
async def simple_upload(
    request: Request,  # noqa: ARG001 - kept for middleware/header parity
    session: PracticeSession = Depends(require_session_owner),
    db: AsyncSession = Depends(get_db),
    file: UploadFile = File(..., description="Audio file (webm/mp4/m4a/wav)."),
    mime_type: str = Form(default="audio/m4a", description="MIME type of the recording."),
    duration_ms: int | None = Form(default=None, description="Recording duration in milliseconds."),
    sample_rate: int | None = Form(default=16000, description="Sample rate in Hz."),
    channels: int | None = Form(default=1, description="Number of channels."),
    codec: str | None = Form(default=None, description="Codec hint, e.g. aac, opus."),
) -> SimpleUploadResponse:
    """One-shot multipart upload. Prefer chunked upload for realtime/progressive recording."""
    data = await file.read()
    if len(data) > settings.max_simple_upload_bytes:
        raise ApiError("payload_too_large")
    if not data:
        raise ApiError("audio_upload_failed", details={"reason": "empty file"})

    ext = _ext(codec or mime_type or file.content_type or "audio/m4a")
    audio_id = new_audio_id()
    audio_url = f"private://audio/{session.id}/{audio_id}.{ext}"
    dest = settings.audio_dir / session.id / f"{audio_id}.{ext}"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(data)

    upload = AudioUpload(
        id=audio_id,
        session_id=session.id,
        upload_id=audio_id,
        audio_url=audio_url,
        mime_type=mime_type or file.content_type or "audio/m4a",
        duration_ms=duration_ms,
        sample_rate=sample_rate,
        channels=channels,
        size_bytes=len(data),
        status="uploaded",
        completed_at=_now(),
    )
    db.add(upload)
    await db.commit()

    await hub.broadcast(
        session.id,
        "audio.uploaded",
        audio_uploaded(upload.id, upload.audio_url, upload.duration_ms),
    )
    return SimpleUploadResponse(audio=_audio_out(upload))


@router.post(
    "/{session_id}/audio/chunks/init",
    response_model=ChunkInitResponse,
    summary="Initialize a chunked upload",
)
async def chunk_init(
    body: ChunkInitRequest,
    session: PracticeSession = Depends(require_session_owner),
    db: AsyncSession = Depends(get_db),
) -> ChunkInitResponse:
    """Start a chunked upload and receive an `uploadId` + chunk size + expiry."""
    upload = AudioUpload(
        id=new_audio_id(),
        session_id=session.id,
        upload_id=new_upload_id(),
        mime_type=body.mime_type,
        sample_rate=body.sample_rate,
        channels=body.channels,
        status="initialized",
    )
    db.add(upload)
    await db.commit()

    # Real expiry is driven by the realtime token TTL; surface a hint timestamp.
    expires_at = (
        datetime.now(timezone.utc) + timedelta(seconds=settings.realtime_token_ttl_seconds)
    ).strftime("%Y-%m-%dT%H:%M:%SZ")

    return ChunkInitResponse(
        upload=ChunkUploadConfig(
            upload_id=upload.upload_id,
            session_id=session.id,
            chunk_size_bytes=body.expected_chunk_size_bytes or settings.chunk_size_bytes,
            expires_at=expires_at,
        )
    )


@router.post(
    "/{session_id}/audio/chunks/{upload_id}",
    response_model=ChunkPartResponse,
    summary="Upload one chunk",
)
async def chunk_part(
    request: Request,
    upload_id: str,
    session: PracticeSession = Depends(require_session_owner),
    db: AsyncSession = Depends(get_db),
) -> ChunkPartResponse:
    """Upload a single `application/octet-stream` chunk.

    Send `X-Chunk-Index`, `X-Chunk-Start-Ms`, `X-Chunk-End-Ms`,
    `X-Chunk-Checksum-Sha256` headers. Re-uploading the same index with a matching
    checksum is idempotent; a mismatched checksum fails with `audio_upload_failed`.
    """
    upload = await _resolve_upload(db, session.id, upload_id)
    if upload.status in {"uploaded", "aborted"}:
        raise ApiError("audio_upload_failed", details={"status": upload.status})

    body = await request.body()
    index = int(request.headers.get("X-Chunk-Index", "0"))
    start_ms = int(request.headers.get("X-Chunk-Start-Ms", "0"))
    end_ms = int(request.headers.get("X-Chunk-End-Ms", "0"))
    expected_checksum = request.headers.get("X-Chunk-Checksum-Sha256", "")

    if expected_checksum and upload_store.sha256_hex(body) != expected_checksum:
        raise ApiError(
            "audio_upload_failed", details={"reason": "checksum mismatch", "index": index}
        )

    # Idempotency: same index already received?
    existing = await db.scalar(
        select(AudioChunk).where(
            AudioChunk.audio_upload_id == upload.id,
            AudioChunk.chunk_index == index,
        )
    )
    if existing is not None:
        if not expected_checksum or existing.checksum_sha256 == expected_checksum:
            return ChunkPartResponse(
                chunk={
                    "upload_id": upload.upload_id,
                    "index": index,
                    "received": True,
                    "received_bytes": existing.size_bytes,
                }
            )
        raise ApiError("audio_upload_failed", details={"reason": "index conflict", "index": index})

    upload_store.write_part(upload.upload_id, index, body)

    chunk = AudioChunk(
        id=new_id("chunk"),
        audio_upload_id=upload.id,
        chunk_index=index,
        start_ms=start_ms,
        end_ms=end_ms,
        size_bytes=len(body),
        checksum_sha256=expected_checksum,
        storage_key=str(upload_store.part_path(upload.upload_id, index)),
    )
    db.add(chunk)
    upload.status = "uploading"
    try:
        await db.commit()
    except IntegrityError as exc:  # concurrent duplicate index
        await db.rollback()
        raise ApiError(
            "audio_upload_failed", details={"reason": "index conflict", "index": index}
        ) from exc

    received = upload_store.list_part_indices(upload.upload_id)
    progress = min(99, len(received) * 8)
    await hub.broadcast(
        session.id,
        "audio.chunk.received",
        audio_chunk_received(upload.upload_id, index, len(body), progress),
    )
    return ChunkPartResponse(
        chunk={
            "upload_id": upload.upload_id,
            "index": index,
            "received": True,
            "received_bytes": len(body),
        }
    )


@router.post(
    "/{session_id}/audio/chunks/{upload_id}/complete",
    response_model=ChunkCompleteResponse,
    summary="Finish a chunked upload",
)
async def chunk_complete(
    body: ChunkCompleteRequest,
    upload_id: str,
    session: PracticeSession = Depends(require_session_owner),
    db: AsyncSession = Depends(get_db),
) -> ChunkCompleteResponse:
    """Assemble all chunks in order into the final audio.

    Missing chunks fail with `audio_chunk_missing`; a wrong `finalChecksumSha256`
    fails with `audio_upload_failed`. Broadcasts `audio.uploaded` over WebSocket.
    """
    upload = await _resolve_upload(db, session.id, upload_id)
    indices = upload_store.list_part_indices(upload.upload_id)
    expected = list(range(body.total_chunks))
    if indices != expected:
        missing = sorted(set(expected) - set(indices))
        raise ApiError(
            "audio_chunk_missing",
            details={"missing": missing, "received": indices},
        )

    ext = _ext(upload.mime_type)
    dest = settings.audio_dir / session.id / f"{upload.id}.{ext}"
    total_bytes = upload_store.assemble(upload.upload_id, dest)

    if body.final_checksum_sha256:
        if upload_store.file_sha256(dest) != body.final_checksum_sha256:
            raise ApiError("audio_upload_failed", details={"reason": "final checksum mismatch"})

    upload.audio_url = f"private://audio/{session.id}/{upload.id}.{ext}"
    upload.size_bytes = total_bytes
    upload.duration_ms = body.duration_ms
    upload.status = "uploaded"
    upload.completed_at = _now()
    await db.commit()

    upload_store.remove(upload.upload_id)
    await hub.broadcast(
        session.id,
        "audio.uploaded",
        audio_uploaded(upload.id, upload.audio_url, upload.duration_ms),
    )
    return ChunkCompleteResponse(audio=_audio_out(upload))


@router.post(
    "/{session_id}/audio/chunks/{upload_id}/abort",
    response_model=ChunkAbortResponse,
    summary="Abort a chunked upload",
)
async def chunk_abort(
    upload_id: str,
    session: PracticeSession = Depends(require_session_owner),
    db: AsyncSession = Depends(get_db),
) -> ChunkAbortResponse:
    """Discard uploaded chunks and mark the upload aborted."""
    upload = await _resolve_upload(db, session.id, upload_id)
    upload_store.remove(upload.upload_id)
    upload.status = "aborted"
    await db.commit()
    return ChunkAbortResponse(upload_id=upload.upload_id, status="aborted")
