from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from api.core.ids import new_event_id


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def build_event(
    session_id: str, event_type: str, payload: dict[str, Any] | None = None
) -> dict[str, Any]:
    """Build a server event envelope (§11.1)."""
    return {
        "type": event_type,
        "sessionId": session_id,
        "eventId": new_event_id(),
        "timestamp": _now(),
        "payload": payload or {},
    }


# --- Server event payload builders (§11.3). ---


def session_ready(status: str) -> dict:
    return {"status": status}


def recording_started_ack(status: str = "recording") -> dict:
    return {"status": status}


def audio_chunk_received(
    upload_id: str, chunk_index: int, received_bytes: int, progress: int
) -> dict:
    return {
        "uploadId": upload_id,
        "chunkIndex": chunk_index,
        "receivedBytes": received_bytes,
        "progress": progress,
    }


def audio_uploading(progress: int) -> dict:
    return {"progress": progress}


def audio_uploaded(audio_id: str, audio_url: str, duration_ms: int | None) -> dict:
    return {"audioId": audio_id, "audioUrl": audio_url, "durationMs": duration_ms}


def evaluation_queued(position: int = 1) -> dict:
    return {"position": position}


def evaluation_processing(progress: int, message: str = "") -> dict:
    return {"progress": progress, "message": message}


def evaluation_completed(result_id: str) -> dict:
    return {"resultId": result_id}


def evaluation_failed(error_code: str, message: str, retryable: bool) -> dict:
    return {"errorCode": error_code, "message": message, "retryable": retryable}


def session_snapshot(
    status: str,
    upload_id: str | None,
    received_chunks: list[int],
    audio_id: str | None,
    result_id: str | None,
) -> dict:
    return {
        "status": status,
        "uploadId": upload_id,
        "receivedChunks": received_chunks,
        "audioId": audio_id,
        "resultId": result_id,
    }
