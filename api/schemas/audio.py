from __future__ import annotations

from pydantic import Field

from api.schemas.common import CamelModel


class AudioOut(CamelModel):
    id: str = Field(description="Audio id.")
    session_id: str = Field(description="Owning session id.")
    audio_url: str | None = Field(
        default=None, description="Private audio URL, e.g. private://audio/..."
    )
    duration_ms: int | None = Field(default=None, description="Duration in milliseconds, if known.")
    mime_type: str = Field(description="MIME type.")
    size_bytes: int | None = Field(default=None, description="Size in bytes, if known.")
    status: str = Field(description="initialized | uploading | uploaded | failed | aborted.")


class SimpleUploadResponse(CamelModel):
    audio: AudioOut


class ChunkInitRequest(CamelModel):
    mime_type: str = Field(
        default="audio/webm", description="MIME type of the recording.", examples=["audio/webm"]
    )
    duration_limit_ms: int = Field(
        default=120_000, description="Max recording duration in ms.", examples=[120000]
    )
    sample_rate: int = Field(default=16_000, description="Sample rate in Hz.", examples=[16000])
    channels: int = Field(default=1, description="Number of channels.", examples=[1])
    expected_chunk_size_bytes: int | None = Field(
        default=None,
        description="Desired chunk size; falls back to the server default.",
        examples=[32768],
    )


class ChunkUploadConfig(CamelModel):
    upload_id: str = Field(description="Opaque upload session id.")
    session_id: str = Field(description="Owning practice session id.")
    chunk_size_bytes: int = Field(description="Effective chunk size in bytes.")
    expires_at: str = Field(description="ISO-8601 UTC expiry timestamp.")


class ChunkInitResponse(CamelModel):
    upload: ChunkUploadConfig


class ChunkPartOut(CamelModel):
    upload_id: str = Field(description="Upload session id.")
    index: int = Field(description="Chunk index acknowledged.")
    received: bool = Field(description="Whether the chunk was accepted.")
    received_bytes: int = Field(description="Bytes received for this chunk.")


class ChunkPartResponse(CamelModel):
    chunk: ChunkPartOut


class ChunkCompleteRequest(CamelModel):
    total_chunks: int = Field(description="Expected total number of chunks.")
    duration_ms: int | None = Field(default=None, description="Total recording duration in ms.")
    final_checksum_sha256: str | None = Field(
        default=None, description="Optional sha256 of the assembled audio."
    )


class ChunkCompleteResponse(CamelModel):
    audio: AudioOut


class ChunkAbortResponse(CamelModel):
    upload_id: str = Field(description="Upload session id that was aborted.")
    status: str = Field(default="aborted", description="Upload status.")
