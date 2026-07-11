from __future__ import annotations

from pydantic import Field

from api.schemas.common import CamelModel


class Segment(CamelModel):
    index: int = Field(description="Zero-based word index within the item.")
    text: str = Field(description="Arabic word token.")
    start_char: int = Field(description="Start char offset into arabic_text.")
    end_char: int = Field(description="End char offset into arabic_text.")


class PracticeItemOut(CamelModel):
    id: str = Field(description="Item id, e.g. `ad_dhuha_1` or `letter_3`.")
    surah_name: str = Field(description="Surah latin name (`Uji Huruf` for drills).")
    surah_number: int = Field(description="Surah number (0 for letter drills).")
    ayah_label: str = Field(description="Ayah label, e.g. `Ayat 1`.")
    ayah_number_start: int = Field(description="First ayah number.")
    ayah_number_end: int = Field(description="Last ayah number.")
    arabic_name: str = Field(description="Arabic surah name.")
    arabic_text: str = Field(description="Arabic (Uthmani) text.")
    translation: str | None = Field(
        default=None, description="Indonesian translation, if available."
    )
    latin_hint: str | None = Field(default=None, description="Latin transliteration hint, if any.")
    focus: str | None = Field(default=None, description="Focus letter hint, e.g. `Huruf ض`.")
    level: str = Field(default="beginner", description="beginner | intermediate | advanced.")
    estimated_minutes: int = Field(default=5, description="Estimated practice minutes.")
    reference_audio_url: str = Field(description="Private reference audio URL/path.")
    is_daily: bool = Field(default=False, description="Whether this item is a daily pick.")
    tags: list[str] = Field(default_factory=list, description="Tags, e.g. juz30, daily, letters.")


class PracticeItemDetail(CamelModel):
    id: str = Field(description="Item id.")
    surah_name: str = Field(description="Surah latin name.")
    surah_number: int = Field(description="Surah number.")
    ayah_label: str = Field(description="Ayah label.")
    arabic_name: str = Field(description="Arabic surah name.")
    arabic_text: str = Field(description="Arabic (Uthmani) text.")
    translation: str | None = Field(
        default=None, description="Indonesian translation, if available."
    )
    latin_hint: str | None = Field(default=None, description="Latin transliteration hint, if any.")
    focus: str | None = Field(default=None, description="Focus letter hint.")
    level: str = Field(default="beginner", description="beginner | intermediate | advanced.")
    estimated_minutes: int = Field(default=5, description="Estimated practice minutes.")
    reference_audio_url: str = Field(description="Private reference audio URL/path.")
    segments: list[Segment] = Field(default_factory=list, description="Word-level segments.")


class PracticeItemListResponse(CamelModel):
    items: list[PracticeItemOut]
    next_cursor: str | None = Field(
        default=None, description="Opaque cursor for the next page, or null."
    )


class PracticeItemDetailResponse(CamelModel):
    item: PracticeItemDetail
