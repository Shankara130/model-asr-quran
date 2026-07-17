from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import APIRouter, Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from api import __version__
from api.core.errors import ApiError
from api.core.logging import setup_logging
from api.core.middleware import RequestIdMiddleware, register_exception_handlers
from api.db import SessionLocal, get_db, init_db
from api.db.seed import seed_dev_user
from api.docs import DESCRIPTION, TAGS
from api.routers import (
    audio,
    auth,
    evaluate,
    home,
    insights,
    practice_items,
    practice_sessions,
    profile,
)
from api.security import CurrentUser
from api.security.deps import require_auth
from api.services.readiness import readiness_status
from api.services.seed_data import seed_practice_items
from api.settings import REFERENCE_AUDIO_DIR, settings, supabase_auth_enabled
from api.ws.routes import register_realtime

log = logging.getLogger("api")


async def seed_startup_data(db: AsyncSession) -> None:
    if not supabase_auth_enabled():
        await seed_dev_user(db)
    await seed_practice_items(db)


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    log.info("starting %s v%s", settings.app_name, __version__)
    async with asyncio.timeout(settings.startup_timeout_seconds):
        await init_db()
        async with SessionLocal() as db:
            await seed_startup_data(db)
    yield
    log.info("shutdown")


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.app_name,
        version=__version__,
        description=DESCRIPTION,
        openapi_tags=TAGS,
        contact={"name": "Sobat Ngaji"},
        lifespan=lifespan,
    )

    app.add_middleware(RequestIdMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.cors_origins),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    register_exception_handlers(app)

    v1 = APIRouter(prefix="/v1")
    v1.include_router(auth.router)
    v1.include_router(profile.router)
    v1.include_router(home.router)
    v1.include_router(practice_items.router)
    v1.include_router(practice_sessions.router)
    v1.include_router(audio.router)
    v1.include_router(evaluate.router)
    v1.include_router(evaluate.results_router)
    v1.include_router(insights.router)

    # Private reference audio (auth-gated; never public CDN).
    @v1.get(
        "/reference-audio/{file_key}",
        tags=["reference-audio"],
        response_class=FileResponse,
        summary="Stream private reference recitation audio",
    )
    async def reference_audio(
        file_key: str,
        principal: CurrentUser = Depends(require_auth),
        db: AsyncSession = Depends(get_db),  # noqa: ARG001 - auth requires the session dep
    ) -> FileResponse:
        """Stream a reference recitation WAV (`{surah:03d}{ayah:03d}`).

        Auth-gated and never exposed on a public CDN. Returns `practice_not_found`
        (404) when the file is not present on this host.
        """
        path = REFERENCE_AUDIO_DIR / f"{file_key}.wav"
        if not path.exists():
            raise ApiError("practice_not_found", "Audio referensi tidak ditemukan.")
        return FileResponse(path, media_type="audio/wav", filename=f"{file_key}.wav")

    @v1.get("/health", tags=["health"], summary="Service health check")
    async def health() -> dict[str, str]:
        """Liveness probe; returns the running version."""
        return {"status": "ok", "version": __version__}

    @v1.get("/readiness", tags=["health"], summary="Dependency readiness check")
    async def readiness() -> JSONResponse:
        """Report whether database, storage, ffmpeg, and model files are ready."""
        ready, checks = await readiness_status()
        return JSONResponse(
            status_code=200 if ready else 503,
            content={"status": "ready" if ready else "not_ready", "checks": checks},
        )

    app.include_router(v1)
    register_realtime(app)
    return app
