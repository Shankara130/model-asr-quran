from __future__ import annotations

from pydantic import Field

from api.schemas.common import CamelModel


class DailyQira(CamelModel):
    id: str = Field(description="Daily Qira id, e.g. `daily_ad_dhuha_1`.")
    practice_item_id: str = Field(description="Backing practice item id.")
    surah_name: str = Field(description="Surah latin name.")
    ayah_label: str = Field(description="Ayah label, e.g. `Ayat 1`.")
    arabic_text: str = Field(description="Arabic (Uthmani) text to recite.")
    translation: str | None = Field(
        default=None, description="Indonesian translation, if available."
    )
    reciter: str | None = Field(default=None, description="Reference reciter name.")
    estimated_minutes: int = Field(default=5, description="Estimated practice minutes.")
    focus: str | None = Field(default=None, description="Focus letter hint, e.g. `Huruf ض`.")


class Greeting(CamelModel):
    headline: str = Field(description="Localized greeting headline.")
    message: str = Field(description="Localized context message.")


class WeeklySnapshot(CamelModel):
    sessions_done: int = Field(default=0, description="Completed sessions this week.")
    sessions_target: int = Field(default=7, description="Weekly session target.")
    average_match: int = Field(default=0, description="Average match score this week.")
    streak_days: int = Field(default=0, description="Current streak in days.")


class ContinuePractice(CamelModel):
    practice_id: str | None = Field(default=None, description="Item to continue, if any.")
    surah_name: str | None = Field(default=None, description="Surah latin name.")
    ayah_label: str | None = Field(default=None, description="Ayah/phrase label.")
    last_match: int | None = Field(default=None, description="Last match score, if any.")


class Recommendation(CamelModel):
    practice_id: str = Field(description="Recommended practice item id.")
    title: str = Field(description="Recommendation title (ID).")
    reason: str = Field(description="Why this is recommended (ID).")


class HomeResponse(CamelModel):
    daily_qira: DailyQira
    greeting: Greeting
    weekly_snapshot: WeeklySnapshot
    continue_practice: ContinuePractice
    recommendation: Recommendation
