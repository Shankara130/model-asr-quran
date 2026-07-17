from __future__ import annotations

import shutil
from pathlib import Path

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from api.db.models import AudioUpload, EvaluationResult, PracticeSession
from api.settings import settings


def purge_directory_contents(directory: Path) -> int:
    directory.mkdir(parents=True, exist_ok=True)
    removed = 0
    for entry in directory.iterdir():
        try:
            if entry.is_dir():
                shutil.rmtree(entry)
            else:
                entry.unlink()
            removed += 1
        except OSError:
            continue
    return removed


async def cleanup_orphaned_runtime_data(db: AsyncSession) -> dict[str, int]:
    removed = purge_directory_contents(settings.uploads_dir)
    removed += purge_directory_contents(settings.audio_dir)

    uploads = await db.execute(
        update(AudioUpload)
        .where(AudioUpload.audio_url.is_not(None))
        .values(audio_url=None, storage_key=None, status="failed")
    )
    evaluations = await db.execute(
        update(EvaluationResult)
        .where(EvaluationResult.status.in_(("queued", "processing")))
        .values(status="failed", error_code="evaluation_failed")
    )
    sessions = await db.execute(
        update(PracticeSession)
        .where(PracticeSession.status.in_(("recording", "uploading", "processing")))
        .values(status="failed")
    )
    await db.commit()
    return {
        "filesystem_entries": removed,
        "uploads": uploads.rowcount or 0,
        "evaluations": evaluations.rowcount or 0,
        "sessions": sessions.rowcount or 0,
    }
