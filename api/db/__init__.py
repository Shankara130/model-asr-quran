from __future__ import annotations

from collections.abc import AsyncIterator

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from api.settings import settings


class Base(DeclarativeBase):
    pass


engine = create_async_engine(
    settings.database_url,
    echo=False,
    future=True,
    connect_args={"check_same_thread": False},
)

SessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


def is_sqlite() -> bool:
    return engine.url.get_backend_name().startswith("sqlite")


async def get_db() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency yielding an async session with FK enforcement on."""
    async with SessionLocal() as session:
        if is_sqlite():
            await session.execute(text("PRAGMA foreign_keys=ON"))
        yield session


async def init_db() -> None:
    """Create the SQLite file, tables, and enable WAL (persists per-file)."""
    settings.uploads_dir.mkdir(parents=True, exist_ok=True)
    settings.audio_dir.mkdir(parents=True, exist_ok=True)

    async with engine.begin() as conn:
        if is_sqlite():
            await conn.execute(text("PRAGMA journal_mode=WAL"))
        await conn.run_sync(Base.metadata.create_all)
