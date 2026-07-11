from __future__ import annotations

from pydantic import Field

from api.schemas.common import CamelModel


class ProfileUser(CamelModel):
    id: str = Field(description="User id.")
    name: str = Field(description="Display name.")
    email: str = Field(description="Unique email.")
    avatar_url: str | None = Field(default=None, description="Avatar URL, if set.")
    learning_level: str = Field(
        default="beginner", description="beginner | intermediate | advanced."
    )


class ProfileSummary(CamelModel):
    total_sessions: int = Field(default=0, description="Lifetime session count.")
    average_score: int = Field(
        default=0, description="Average match score across completed sessions."
    )
    focus_letter: str | None = Field(default=None, description="Lowest-mastery Arabic letter.")
    streak_days: int = Field(default=0, description="Current consecutive-day streak.")
    learning_summary: str = Field(default="", description="AI-generated one-line summary (ID).")
    achievement: str | None = Field(default=None, description="Latest achievement headline (ID).")


class Preferences(CamelModel):
    practice_level: str = Field(
        default="beginner", description="beginner | intermediate | advanced."
    )
    practice_mode: str = Field(default="phrases", description="letters | phrases | verses.")
    audio_feedback_enabled: bool = Field(default=True, description="Whether audio feedback is on.")
    daily_report_frequency: str = Field(
        default="weekly_sunday", description="Report cadence, e.g. weekly_sunday."
    )
    reminder_enabled: bool = Field(default=False, description="Whether practice reminders are on.")
    reminder_time: str | None = Field(
        default=None, description="Reminder time `HH:MM`, or null when disabled."
    )


class ProfileResponse(CamelModel):
    user: ProfileUser
    summary: ProfileSummary
    preferences: Preferences


class ProfileIdentityRequest(CamelModel):
    name: str | None = Field(default=None, description="New display name (omit to keep).")
    learning_level: str | None = Field(
        default=None, description="beginner | intermediate | advanced (omit to keep)."
    )
    avatar_url: str | None = Field(default=None, description="New avatar URL (omit to keep).")


class ProfileIdentityResponse(CamelModel):
    user: ProfileUser


class PreferencesRequest(CamelModel):
    practice_level: str | None = Field(
        default=None, description="beginner | intermediate | advanced."
    )
    practice_mode: str | None = Field(default=None, description="letters | phrases | verses.")
    audio_feedback_enabled: bool | None = Field(default=None, description="Toggle audio feedback.")
    daily_report_frequency: str | None = Field(default=None, description="Report cadence.")
    reminder_enabled: bool | None = Field(default=None, description="Toggle reminders.")
    reminder_time: str | None = Field(default=None, description="Reminder time `HH:MM` or null.")


class PreferencesResponse(CamelModel):
    preferences: Preferences
