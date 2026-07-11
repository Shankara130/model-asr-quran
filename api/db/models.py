from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import JSON, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from api.db import Base


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String, default="")
    email: Mapped[str] = mapped_column(String, unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String, default="dev-stub")  # sentinel (no bcrypt)
    avatar_url: Mapped[str | None] = mapped_column(String, nullable=True)
    learning_level: Mapped[str] = mapped_column(String, default="beginner")
    created_at: Mapped[str] = mapped_column(String, default=now_iso)
    updated_at: Mapped[str] = mapped_column(String, default=now_iso, onupdate=now_iso)

    preferences: Mapped[UserPreference | None] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class AuthRefreshToken(Base):
    __tablename__ = "auth_refresh_tokens"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    token_hash: Mapped[str] = mapped_column(String, unique=True, index=True)
    issued_at: Mapped[str] = mapped_column(String, default=now_iso)
    expires_at: Mapped[str] = mapped_column(String)
    revoked_at: Mapped[str | None] = mapped_column(String, nullable=True)


class UserPreference(Base):
    __tablename__ = "user_preferences"

    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    practice_level: Mapped[str] = mapped_column(String, default="beginner")
    practice_mode: Mapped[str] = mapped_column(String, default="phrases")
    audio_feedback_enabled: Mapped[bool] = mapped_column(default=True)
    daily_report_frequency: Mapped[str] = mapped_column(String, default="weekly_sunday")
    reminder_enabled: Mapped[bool] = mapped_column(default=False)
    reminder_time: Mapped[str | None] = mapped_column(String, nullable=True)
    updated_at: Mapped[str] = mapped_column(String, default=now_iso, onupdate=now_iso)

    user: Mapped[User] = relationship(back_populates="preferences")


class PracticeItem(Base):
    __tablename__ = "practice_items"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    surah_name: Mapped[str] = mapped_column(String, default="")
    surah_number: Mapped[int] = mapped_column(Integer, default=0)
    ayah_label: Mapped[str] = mapped_column(String, default="")
    ayah_number_start: Mapped[int] = mapped_column(Integer, default=1)
    ayah_number_end: Mapped[int] = mapped_column(Integer, default=1)
    arabic_name: Mapped[str] = mapped_column(String, default="")
    arabic_text: Mapped[str] = mapped_column(String, default="")
    translation: Mapped[str | None] = mapped_column(String, nullable=True)
    latin_hint: Mapped[str | None] = mapped_column(String, nullable=True)
    focus: Mapped[str] = mapped_column(String, default="")
    level: Mapped[str] = mapped_column(String, default="beginner")
    estimated_minutes: Mapped[int] = mapped_column(Integer, default=5)
    reference_audio_url: Mapped[str] = mapped_column(String, default="")
    is_daily: Mapped[bool] = mapped_column(default=False)
    tags: Mapped[list] = mapped_column(JSON, default=list)
    # Internal (not spec columns): how to resolve target phoneme at eval time.
    kind: Mapped[str] = mapped_column(String, default="verse")  # "verse" | "letter"
    letter_index: Mapped[int | None] = mapped_column(Integer, nullable=True)
    target_phoneme: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[str] = mapped_column(String, default=now_iso)
    updated_at: Mapped[str] = mapped_column(String, default=now_iso, onupdate=now_iso)


class PracticeSession(Base):
    __tablename__ = "practice_sessions"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    practice_item_id: Mapped[str] = mapped_column(ForeignKey("practice_items.id"))
    status: Mapped[str] = mapped_column(String, default="started")
    client_session_id: Mapped[str | None] = mapped_column(String, nullable=True)
    device: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    started_at: Mapped[str] = mapped_column(String, default=now_iso)
    completed_at: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[str] = mapped_column(String, default=now_iso)
    updated_at: Mapped[str] = mapped_column(String, default=now_iso, onupdate=now_iso)

    audio_uploads: Mapped[list[AudioUpload]] = relationship(
        back_populates="session", cascade="all, delete-orphan"
    )
    evaluation_results: Mapped[list[EvaluationResult]] = relationship(
        back_populates="session", cascade="all, delete-orphan"
    )


class AudioUpload(Base):
    __tablename__ = "audio_uploads"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    session_id: Mapped[str] = mapped_column(
        ForeignKey("practice_sessions.id", ondelete="CASCADE"), index=True
    )
    upload_id: Mapped[str] = mapped_column(String, unique=True, index=True)
    audio_url: Mapped[str | None] = mapped_column(String, nullable=True)
    mime_type: Mapped[str] = mapped_column(String, default="audio/webm")
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sample_rate: Mapped[int | None] = mapped_column(Integer, nullable=True)
    channels: Mapped[int | None] = mapped_column(Integer, nullable=True)
    size_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String, default="initialized")
    created_at: Mapped[str] = mapped_column(String, default=now_iso)
    completed_at: Mapped[str | None] = mapped_column(String, nullable=True)

    session: Mapped[PracticeSession] = relationship(back_populates="audio_uploads")
    chunks: Mapped[list[AudioChunk]] = relationship(
        back_populates="upload", cascade="all, delete-orphan"
    )


class AudioChunk(Base):
    __tablename__ = "audio_chunks"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    audio_upload_id: Mapped[str] = mapped_column(
        ForeignKey("audio_uploads.id", ondelete="CASCADE"), index=True
    )
    chunk_index: Mapped[int] = mapped_column(Integer)
    start_ms: Mapped[int] = mapped_column(Integer, default=0)
    end_ms: Mapped[int] = mapped_column(Integer, default=0)
    size_bytes: Mapped[int] = mapped_column(Integer, default=0)
    checksum_sha256: Mapped[str] = mapped_column(String, default="")
    storage_key: Mapped[str] = mapped_column(String, default="")
    received_at: Mapped[str] = mapped_column(String, default=now_iso)

    upload: Mapped[AudioUpload] = relationship(back_populates="chunks")
    __table_args__ = (
        UniqueConstraint("audio_upload_id", "chunk_index", name="uq_upload_chunk_index"),
    )


class EvaluationResult(Base):
    __tablename__ = "evaluation_results"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    session_id: Mapped[str] = mapped_column(
        ForeignKey("practice_sessions.id", ondelete="CASCADE"), index=True
    )
    practice_item_id: Mapped[str] = mapped_column(ForeignKey("practice_items.id"))
    match_score: Mapped[int] = mapped_column(Integer, default=0)
    confidence_level: Mapped[str] = mapped_column(String, default="low")
    summary: Mapped[str] = mapped_column(String, default="")
    recommendation: Mapped[str] = mapped_column(String, default="")
    prediction: Mapped[str | None] = mapped_column(String, nullable=True)
    status: Mapped[str] = mapped_column(
        String, default="queued"
    )  # queued|processing|completed|failed
    error_code: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[str] = mapped_column(String, default=now_iso, index=True)

    session: Mapped[PracticeSession] = relationship(back_populates="evaluation_results")
    highlights: Mapped[list[AyahHighlight]] = relationship(
        back_populates="result", cascade="all, delete-orphan"
    )
    letter_insights: Mapped[list[LetterInsight]] = relationship(
        back_populates="result", cascade="all, delete-orphan"
    )


class AyahHighlight(Base):
    __tablename__ = "ayah_highlights"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    evaluation_result_id: Mapped[str] = mapped_column(
        ForeignKey("evaluation_results.id", ondelete="CASCADE"), index=True
    )
    segment: Mapped[str] = mapped_column(String, default="")
    status: Mapped[str] = mapped_column(String, default="read")
    note: Mapped[str] = mapped_column(String, default="")
    start_index: Mapped[int] = mapped_column(Integer, default=0)
    end_index: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[str] = mapped_column(String, default=now_iso)

    result: Mapped[EvaluationResult] = relationship(back_populates="highlights")


class LetterInsight(Base):
    __tablename__ = "letter_insights"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    evaluation_result_id: Mapped[str] = mapped_column(
        ForeignKey("evaluation_results.id", ondelete="CASCADE"), index=True
    )
    letter: Mapped[str] = mapped_column(String)
    mastery_score: Mapped[int] = mapped_column(Integer, default=0)
    mistake_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[str] = mapped_column(String, default=now_iso)

    result: Mapped[EvaluationResult] = relationship(back_populates="letter_insights")


class LetterMastery(Base):
    __tablename__ = "letter_mastery"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    letter: Mapped[str] = mapped_column(String)
    score: Mapped[int] = mapped_column(Integer, default=0)
    mistake_count: Mapped[int] = mapped_column(Integer, default=0)
    last_practiced_at: Mapped[str] = mapped_column(String, default=now_iso)
    updated_at: Mapped[str] = mapped_column(String, default=now_iso, onupdate=now_iso)

    __table_args__ = (UniqueConstraint("user_id", "letter", name="uq_user_letter"),)


class WeeklyReport(Base):
    __tablename__ = "weekly_reports"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    week_start: Mapped[str] = mapped_column(String)
    practice_count: Mapped[int] = mapped_column(Integer, default=0)
    average_score: Mapped[int] = mapped_column(Integer, default=0)
    focus_letter: Mapped[str | None] = mapped_column(String, nullable=True)
    summary: Mapped[str] = mapped_column(String, default="")
    trend: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[str] = mapped_column(String, default=now_iso)

    __table_args__ = (UniqueConstraint("user_id", "week_start", name="uq_user_week"),)
