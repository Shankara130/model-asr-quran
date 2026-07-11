from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel


class CamelModel(BaseModel):
    """JSON keys are camelCase (spec); code uses snake_case."""

    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        from_attributes=True,
        extra="ignore",
    )


# --- Enums (allowed values from the spec). ---


class LearningLevel(str, Enum):
    beginner = "beginner"
    intermediate = "intermediate"
    advanced = "advanced"


class ConfidenceLevel(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"


class HighlightStatus(str, Enum):
    read = "read"
    current = "current"
    needs_check = "needs_check"
    needs_retry = "needs_retry"


class SessionStatus(str, Enum):
    started = "started"
    recording = "recording"
    uploading = "uploading"
    processing = "processing"
    completed = "completed"
    failed = "failed"
    cancelled = "cancelled"


class AudioStatus(str, Enum):
    initialized = "initialized"
    uploading = "uploading"
    uploaded = "uploaded"
    failed = "failed"
    aborted = "aborted"


class EvalStatus(str, Enum):
    queued = "queued"
    processing = "processing"
    completed = "completed"
    failed = "failed"


class PracticeMode(str, Enum):
    letters = "letters"
    phrases = "phrases"
    verses = "verses"
