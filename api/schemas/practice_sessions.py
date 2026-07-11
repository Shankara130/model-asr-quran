from __future__ import annotations

from pydantic import Field

from api.schemas.common import CamelModel


class DeviceInfo(CamelModel):
    platform: str | None = Field(default=None, description="android | ios | web.")
    model: str | None = Field(default=None, description="Device model.")
    app_version: str | None = Field(default=None, description="App version.")


class CreateSessionRequest(CamelModel):
    practice_item_id: str = Field(
        description="Id of the practice item to recite.", examples=["ad_dhuha_1"]
    )
    client_session_id: str | None = Field(
        default=None,
        description="Optional client-side correlation id.",
        examples=["client_uuid_001"],
    )
    device: DeviceInfo | None = Field(default=None, description="Optional device info.")


class RealtimeConfig(CamelModel):
    url: str = Field(description="WebSocket URL for this session.")
    token: str = Field(description="Short-lived realtime token (passed as `?token=`).")
    expires_in: int = Field(description="Realtime token lifetime in seconds.")


class UploadConfig(CamelModel):
    mode: str = Field(default="chunked", description="Upload mode (`chunked`).")
    chunk_size_bytes: int = Field(description="Suggested chunk size in bytes.")
    accepted_mime_types: list[str] = Field(description="Accepted audio MIME types.")
    max_duration_seconds: int = Field(description="Max recording duration in seconds.")


class SessionCreated(CamelModel):
    id: str = Field(description="Session id.")
    practice_item_id: str = Field(description="Practice item id.")
    user_id: str = Field(description="Owning user id.")
    status: str = Field(default="started", description="Session status.")
    created_at: str = Field(description="ISO-8601 UTC creation timestamp.")
    expires_at: str = Field(description="ISO-8601 UTC expiry timestamp.")


class CreateSessionResponse(CamelModel):
    session: SessionCreated
    realtime: RealtimeConfig
    upload: UploadConfig


class SessionFetched(CamelModel):
    id: str = Field(description="Session id.")
    practice_item_id: str = Field(description="Practice item id.")
    status: str = Field(description="Session status.")
    audio_url: str | None = Field(default=None, description="Latest uploaded audio URL, if any.")
    created_at: str = Field(description="ISO-8601 UTC creation timestamp.")
    completed_at: str | None = Field(
        default=None, description="ISO-8601 UTC completion timestamp, if any."
    )


class GetSessionResponse(CamelModel):
    session: SessionFetched


class SessionCancelled(CamelModel):
    id: str = Field(description="Session id.")
    status: str = Field(default="cancelled", description="Session status.")


class CancelSessionResponse(CamelModel):
    session: SessionCancelled


class SessionHistoryItem(CamelModel):
    id: str = Field(description="Session id.")
    practice_item_id: str = Field(description="Practice item id.")
    surah_name: str = Field(description="Surah latin name.")
    ayah_label: str = Field(description="Ayah label.")
    status: str = Field(description="Session status.")
    match_score: int | None = Field(default=None, description="Latest match score, if completed.")
    confidence_level: str | None = Field(
        default=None, description="low | medium | high, if completed."
    )
    created_at: str = Field(description="ISO-8601 UTC creation timestamp.")
    completed_at: str | None = Field(
        default=None, description="ISO-8601 UTC completion timestamp, if any."
    )


class SessionHistoryResponse(CamelModel):
    items: list[SessionHistoryItem]
    next_cursor: str | None = Field(
        default=None, description="Opaque cursor for the next page, or null."
    )
