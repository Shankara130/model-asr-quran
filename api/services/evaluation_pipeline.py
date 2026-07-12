from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from api.core.errors import ApiError
from api.core.ids import new_id, new_result_id
from api.db import SessionLocal, is_sqlite
from api.db.models import (
    AudioUpload,
    AyahHighlight,
    EvaluationResult,
    LetterInsight,
    PracticeItem,
    PracticeSession,
)
from api.services import asr_provider, audio_codec, letter_mastery, quran_provider, result_mapper
from api.services.asr_provider import ModelUnavailable
from api.settings import settings
from api.ws.events import (
    evaluation_completed,
    evaluation_failed,
    evaluation_processing,
    evaluation_queued,
)
from api.ws.hub import hub
from web.services.evaluation_service import evaluate_prediction
from web.services.letter_test_service import LETTER_TESTS

log = logging.getLogger("api.eval")

# Serialize CPU-heavy ASR on M1 8GB (avoid OOM / model reentry).
_semaphore = asyncio.Semaphore(1)
_LETTER_TARGETS = {f"letter_{test['index']}": test["target_phoneme"] for test in LETTER_TESTS}


def _iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _audio_path(audio_url: str | None) -> Path | None:
    if not audio_url:
        return None
    prefix = "private://audio/"
    if audio_url.startswith(prefix):
        return settings.audio_dir / audio_url[len(prefix) :]
    return None


async def _resolve_audio(db: AsyncSession, session_id: str, audio_id: str | None) -> AudioUpload:
    if audio_id:
        upload = await db.scalar(
            select(AudioUpload).where(
                AudioUpload.session_id == session_id,
                AudioUpload.id == audio_id,
            )
        )
    else:
        upload = await db.scalar(
            select(AudioUpload)
            .where(AudioUpload.session_id == session_id, AudioUpload.status == "uploaded")
            .order_by(AudioUpload.completed_at.desc())
            .limit(1)
        )
    if upload is None or upload.status != "uploaded" or not upload.audio_url:
        raise ApiError("audio_unprocessable", "Audio belum diunggah untuk sesi ini.")
    return upload


def _run_blocking(item_info: dict, audio_path: Path | None) -> tuple[dict, str]:
    if audio_path is None or not audio_path.exists():
        raise ApiError("audio_unprocessable", "File audio tidak ditemukan.")

    samples = audio_codec.decode_any(audio_path)
    asr = asr_provider.get_asr()
    stream = asr.create_stream()
    asr.accept_audio(stream, samples.tobytes())
    prediction = asr.finish_stream(stream)

    if item_info.get("kind") == "letter":
        target_phoneme = item_info.get("target_phoneme") or ""
    else:
        quran = quran_provider.get_quran()
        verse = quran.get_verse(item_info["surah"], item_info["ayah"])
        target_phoneme = verse["target_phoneme"]

    raw = evaluate_prediction(target_phoneme, prediction)
    mapped = result_mapper.map_result(raw, item_info)
    return mapped, prediction


async def create_evaluation(
    session_id: str, audio_id: str | None = None
) -> tuple[str, dict, str | None, str]:
    """Set up a queued result row, mark the session processing, and broadcast start events.

    Returns ``(result_id, item_info, audio_url, user_id)`` so a caller can run the
    heavy work synchronously (WS) or as a background task (REST).
    """
    async with SessionLocal() as db:
        if is_sqlite():
            await db.execute(text("PRAGMA foreign_keys=ON"))
        session = await db.get(PracticeSession, session_id)
        if session is None:
            raise ApiError("session_not_found")
        if session.status == "cancelled":
            raise ApiError("session_invalid_state")
        item = await db.get(PracticeItem, session.practice_item_id)
        if item is None:
            raise ApiError("practice_not_found")
        upload = await _resolve_audio(db, session_id, audio_id)

        result = EvaluationResult(
            id=new_result_id(),
            session_id=session.id,
            practice_item_id=item.id,
            status="queued",
        )
        db.add(result)
        session.status = "processing"
        session.updated_at = _iso()
        await db.commit()
        result_id = result.id

        item_info = {
            "arabic_text": item.arabic_text,
            "kind": "letter" if item.id in _LETTER_TARGETS else "verse",
            "surah": item.surah_number,
            "ayah": item.ayah_number_start,
            "target_phoneme": _LETTER_TARGETS.get(item.id),
        }

    await hub.broadcast(session_id, "evaluation.queued", evaluation_queued(1))
    await hub.broadcast(
        session_id,
        "evaluation.processing",
        evaluation_processing(10, "AI sedang mencocokkan bacaan dengan referensi."),
    )
    return result_id, item_info, upload.audio_url, session.user_id


async def run_evaluation(
    result_id: str,
    session_id: str,
    item_info: dict,
    audio_url: str | None,
    user_id: str,
) -> None:
    """Run the blocking ASR + mapping off the event loop, then persist + broadcast."""
    audio_path = _audio_path(audio_url)
    async with _semaphore:
        try:
            mapped, prediction = await asyncio.to_thread(_run_blocking, item_info, audio_path)
        except ModelUnavailable as exc:
            await _fail(session_id, result_id, "audio_unprocessable", exc.message, retryable=False)
            return
        except ApiError as exc:
            code = (
                "audio_unprocessable" if exc.code == "audio_unprocessable" else "evaluation_failed"
            )
            await _fail(session_id, result_id, code, exc.message, retryable=True)
            return
        except Exception:
            log.exception("evaluation failed for session %s", session_id)
            await _fail(
                session_id,
                result_id,
                "evaluation_failed",
                "Evaluasi gagal diproses.",
                retryable=True,
            )
            return

    async with SessionLocal() as db:
        if is_sqlite():
            await db.execute(text("PRAGMA foreign_keys=ON"))
        result = await db.get(EvaluationResult, result_id)
        result.match_score = mapped["match_score"]
        result.confidence_level = mapped["confidence_level"]
        result.summary = mapped["summary"]
        result.recommendation = mapped["recommendation"]
        result.status = "completed"
        result.completed_at = _iso()

        for h in mapped["highlights"]:
            db.add(
                AyahHighlight(
                    id=new_id("hl"),
                    evaluation_result_id=result_id,
                    segment=h["segment"],
                    status=h["status"],
                    note=h["note"],
                    start_index=h["start_index"],
                    end_index=h["end_index"],
                )
            )
        for li in mapped["letter_insights"]:
            db.add(
                LetterInsight(
                    id=new_id("li"),
                    evaluation_result_id=result_id,
                    letter=li["letter"],
                    mastery_score=li["mastery_score"],
                    mistake_count=li["mistake_count"],
                )
            )
        await letter_mastery.update_for_result(db, user_id, mapped["letter_insights"])

        session = await db.get(PracticeSession, session_id)
        if session is not None:
            session.status = "completed"
            session.completed_at = _iso()
            session.updated_at = _iso()
        await db.commit()

    await hub.broadcast(session_id, "evaluation.completed", evaluation_completed(result_id))


async def _fail(session_id: str, result_id: str, code: str, message: str, retryable: bool) -> None:
    async with SessionLocal() as db:
        if is_sqlite():
            await db.execute(text("PRAGMA foreign_keys=ON"))
        result = await db.get(EvaluationResult, result_id)
        if result is not None:
            result.status = "failed"
            result.error_code = code
        session = await db.get(PracticeSession, session_id)
        if session is not None and session.status != "cancelled":
            session.status = "failed"
            session.updated_at = _iso()
        await db.commit()
    await hub.broadcast(
        session_id, "evaluation.failed", evaluation_failed(code, message, retryable)
    )


async def evaluate_for_session(session_id: str, audio_id: str | None = None) -> str:
    """Create + run synchronously (used by the WebSocket evaluation.requested event)."""
    result_id, item_info, audio_url, user_id = await create_evaluation(session_id, audio_id)
    await run_evaluation(result_id, session_id, item_info, audio_url, user_id)
    return result_id
