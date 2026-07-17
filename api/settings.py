from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# Project root = parent of the ``api`` package.
PROJECT_ROOT = Path(__file__).resolve().parents[1]

DATA_DIR = PROJECT_ROOT / "data"
VAR_DIR = DATA_DIR / "var"

# Model-independent local sources (always present, even without the ONNX model).
QURAN_TEXT_PATH = DATA_DIR / "raw" / "text" / "quran_uthmani.json"
REFERENCE_AUDIO_DIR = DATA_DIR / "raw" / "audio" / "Husary_128kbps_Mujawwad"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="SOBAT_",
        env_file=".env",
        extra="ignore",
    )

    app_name: str = "Sobat Ngaji API"
    env: str = "dev"

    # Dev auth (HMAC-signed timed tokens; no bcrypt/JWT).
    token_secret: str = "sobat-ngaji-dev-secret-change-me"
    access_token_ttl_seconds: int = 3600
    realtime_token_ttl_seconds: int = 1800

    # Supabase integration. When ``supabase_url`` and ``supabase_anon_key`` are
    # set, REST auth delegates to Supabase Auth. The service role key is optional
    # and should only be used from the backend process.
    supabase_url: str | None = None
    supabase_anon_key: str | None = None
    supabase_service_role_key: str | None = None

    # Evaluation thresholds (tunable).
    confidence_high: int = 85
    confidence_medium: int = 60

    # Persistence (SQLite, zero-infra for M1 dev).
    database_url: str = f"sqlite+aiosqlite:///{VAR_DIR / 'api.db'}"

    # Upload storage.
    uploads_dir: Path = VAR_DIR / "uploads"
    audio_dir: Path = VAR_DIR / "audio"
    max_audio_duration_seconds: int = 120
    max_simple_upload_bytes: int = 25 * 1024 * 1024
    max_ws_chunk_bytes: int = 1 * 1024 * 1024
    chunk_size_bytes: int = 32768
    audio_retention_hours: int = 24

    accepted_mime_types: tuple[str, ...] = (
        "audio/webm",
        "audio/mp4",
        "audio/m4a",
        "audio/x-m4a",
        "audio/wav",
        "audio/x-wav",
        "audio/mpeg",
    )

    # Dev user.
    dev_user_name: str = "Alya Rahma"
    dev_user_email: str = "alya@sobat.ngaji"
    dev_user_level: str = "beginner"

    cors_origins: tuple[str, ...] = ("*",)
    startup_timeout_seconds: int = 30
    readiness_timeout_seconds: int = 10


settings = Settings()


def supabase_auth_enabled() -> bool:
    return bool(settings.supabase_url and settings.supabase_anon_key)
