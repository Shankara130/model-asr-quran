from __future__ import annotations

from pydantic import Field

from api.schemas.common import CamelModel


class WeeklyLetterMastery(CamelModel):
    letter: str = Field(description="Arabic letter.")
    score: int = Field(description="0–100 mastery score this week.")
    mistake_count: int = Field(description="Mistakes this week.")


class WeeklyInsight(CamelModel):
    practice_count: int = Field(default=0, description="Sessions completed this week.")
    average_score: int = Field(default=0, description="Average match score this week.")
    growth_percent: int = Field(default=0, description="Score change vs the previous week.")
    focus_letter: str | None = Field(default=None, description="Lowest-mastery letter this week.")
    summary: str = Field(default="", description="Localized weekly summary.")
    trend: list[int] = Field(
        default_factory=list, description="7 daily average scores (0 if none)."
    )
    letter_mastery: list[WeeklyLetterMastery] = Field(
        default_factory=list, description="Per-letter mastery for the week."
    )
    suggestion: str | None = Field(default=None, description="Localized practice suggestion.")


class WeeklyInsightResponse(CamelModel):
    weekly_insight: WeeklyInsight


class LetterMasteryItem(CamelModel):
    letter: str = Field(description="Arabic letter.")
    score: int = Field(description="0–100 rolling mastery score.")
    mistake_count: int = Field(description="Cumulative mistake count.")
    last_practiced_at: str | None = Field(
        default=None, description="ISO-8601 UTC of last practice, if any."
    )


class LetterMasteryResponse(CamelModel):
    items: list[LetterMasteryItem]
