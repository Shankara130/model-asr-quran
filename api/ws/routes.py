from __future__ import annotations

import base64
import binascii
import json
import logging
from datetime import datetime, timezone
from typing import Any

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from sqlalchemy import select

from api.core.errors import ApiError
from api.core.ids import new_id
from api.db import SessionLocal
from api.db.models import AudioChunk, AudioUpload, EvaluationResult, PracticeSession
from api.security.tokens import verify_realtime_token
from api.services import upload_store
from api.settings import settings
from api.ws.events import (
    audio_chunk_received,
    recording_started_ack,
    session_ready,
)
from api.ws.hub import hub

log = logging.getLogger("api.ws")


def _now() -> datetime:
    return datetime.now(timezone.utc)


async def _set_session_status(session_id: str, status: str) -> None:
    async with SessionLocal() as db:
        session = await db.get(PracticeSession, session_id)
        if session is not None:
            session.status = status
            session.updated_at = _now()
            await db.commit()


async def _trigger_evaluation(session_id: str, audio_id: str | None) -> None:
    from api.services.evaluation_pipeline import evaluate_for_session

    await evaluate_for_session(session_id=session_id, audio_id=audio_id)


def register_realtime(app: FastAPI) -> None:
    @app.websocket("/v1/realtime/practice-sessions/{session_id}")
    async def realtime(websocket: WebSocket, session_id: str) -> None:
        token = websocket.query_params.get("token", "")

        async with SessionLocal() as db:
            session = await db.get(PracticeSession, session_id)

        valid = session is not None
        if valid:
            try:
                verify_realtime_token(token, session_id, session.user_id)  # type: ignore[union-attr]
            except ApiError:
                valid = False

        if not valid:
            await websocket.accept()
            await websocket.close(code=4401)
            return

        await websocket.accept()
        await hub.register(session_id, websocket)
        await websocket.send_json(
            {
                "type": "session.ready",
                "sessionId": session_id,
                "payload": session_ready(session.status),  # type: ignore[union-attr]
            }
        )

        try:
            while True:
                raw = await websocket.receive_text()
                try:
                    event = json.loads(raw)
                except json.JSONDecodeError:
                    continue
                await _handle_client_event(session_id, websocket, event)
        except WebSocketDisconnect:
            log.debug("ws disconnect session=%s", session_id)
        finally:
            await hub.unregister(session_id, websocket)


async def _handle_client_event(session_id: str, ws: WebSocket, event: dict[str, Any]) -> None:
    event_type = event.get("type")
    payload = event.get("payload") or {}

    if event_type == "ping":
        await ws.send_json({"type": "pong", "sessionId": session_id, "payload": {}})
        return

    if event_type == "recording.started":
        await _set_session_status(session_id, "recording")
        await hub.broadcast(session_id, "recording.started.ack", recording_started_ack("recording"))
        return

    if event_type == "evaluation.requested":
        await ws.send_json(
            {"type": "evaluation.queued", "sessionId": session_id, "payload": {"position": 1}}
        )
        await _trigger_evaluation(session_id, payload.get("audioId"))
        return

    if event_type == "audio.chunk":
        await _handle_ws_audio_chunk(session_id, payload)
        return

    if event_type == "recording.stopped":
        # Audio finalization happens via REST /complete; acknowledged silently.
        return


async def _handle_ws_audio_chunk(session_id: str, payload: dict[str, Any]) -> None:
    upload_id = payload.get("uploadId")
    if not upload_id:
        return
    data_b64 = payload.get("data", "")
    if len(data_b64) > settings.max_ws_chunk_bytes * 2:
        return  # too large; use REST chunk upload instead
    try:
        data = base64.b64decode(data_b64)
    except (binascii.Error, ValueError):
        return
    index = int(payload.get("chunkIndex", 0))

    async with SessionLocal() as db:
        upload = await db.scalar(
            select(AudioUpload).where(
                AudioUpload.upload_id == upload_id,
                AudioUpload.session_id == session_id,
            )
        )
        if upload is None:
            return
        existing = await db.scalar(
            select(AudioChunk).where(
                AudioChunk.audio_upload_id == upload.id,
                AudioChunk.chunk_index == index,
            )
        )
        if existing is not None:
            return  # idempotent skip
        upload_store.write_part(upload.upload_id, index, data)
        db.add(
            AudioChunk(
                id=new_id("chunk"),
                audio_upload_id=upload.id,
                chunk_index=index,
                start_ms=int(payload.get("startMs", 0)),
                end_ms=int(payload.get("endMs", 0)),
                size_bytes=len(data),
                checksum_sha256=payload.get("checksumSha256", ""),
                storage_key=str(upload_store.part_path(upload.upload_id, index)),
            )
        )
        upload.status = "uploading"
        await db.commit()

    received = upload_store.list_part_indices(upload_id)
    await hub.broadcast(
        session_id,
        "audio.chunk.received",
        audio_chunk_received(upload_id, index, len(data), min(99, len(received) * 8)),
    )


# Re-export for snapshot-style consumers if needed later.
_ = EvaluationResult
