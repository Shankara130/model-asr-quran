from __future__ import annotations

import asyncio
import os
import shutil

from sqlalchemy import text

from api.db import SessionLocal
from api.settings import settings


async def readiness_status() -> tuple[bool, dict[str, dict[str, bool]]]:
    checks = {
        "database": {"ready": False},
        "storage": {"ready": False},
        "ffmpeg": {"ready": False},
        "model": {"ready": False},
    }

    try:
        async with asyncio.timeout(settings.readiness_timeout_seconds):
            async with SessionLocal() as db:
                checks["database"]["ready"] = (await db.execute(text("select 1"))).scalar_one() == 1
    except Exception:
        pass

    checks["storage"]["ready"] = all(
        path.is_dir() and os.access(path, os.W_OK)
        for path in (settings.uploads_dir, settings.audio_dir)
    )
    checks["ffmpeg"]["ready"] = shutil.which("ffmpeg") is not None

    try:
        from web.config import validate_required_files

        validate_required_files()
        checks["model"]["ready"] = True
    except (FileNotFoundError, ImportError):
        pass

    return all(component["ready"] for component in checks.values()), checks
