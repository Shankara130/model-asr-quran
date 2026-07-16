from __future__ import annotations

from pydantic import Field

from api.schemas.common import CamelModel


class EvaluateRequest(CamelModel):
    audio_id: str | None = Field(
        default=None, description="Specific uploaded audio id; omit to use the latest upload."
    )
    audio_url: str | None = Field(
        default=None, description="Audio URL (accepted, audio_id preferred)."
    )


class EvaluateEvaluation(CamelModel):
    result_id: str = Field(description="Evaluation result id.")
    session_id: str = Field(description="Owning session id.")
    status: str = Field(default="queued", description="Evaluation status (queued).")


class EvaluateResponse(CamelModel):
    evaluation: EvaluateEvaluation


class EvaluationHighlightOut(CamelModel):
    segment: str = Field(description="Arabic word segment.")
    status: str = Field(description="read | current | needs_check | needs_retry.")
    note: str = Field(description="Localized note explaining the status.")
    start_index: int = Field(description="Start char offset into the item's arabic_text.")
    end_index: int = Field(description="End char offset into the item's arabic_text.")


class LetterInsightOut(CamelModel):
    letter: str = Field(description="Arabic letter.")
    mastery_score: int = Field(description="0–100 mastery score for this result.")
    mistake_count: int = Field(description="Number of mistakes attributed to this letter.")


class SelfCorrectionOut(CamelModel):
    type: str = Field(description="Self-correction event type.")
    detected: str = Field(description="Superseded detected phoneme segment.")
    selected: str = Field(description="Phoneme segment selected for final evaluation.")
    note: str = Field(description="Localized note explaining the correction handling.")


class EvaluationResultOut(CamelModel):
    result_id: str = Field(description="Evaluation result id.")
    session_id: str = Field(description="Session id.")
    practice_item_id: str = Field(description="Practice item id.")
    attempt_number: int = Field(default=1, description="1-based evaluation attempt number.")
    is_latest: bool = Field(default=True, description="Whether this is the latest session result.")
    match_score: int = Field(description="0–100 match score (rounded similarity).")
    confidence_level: str = Field(description="low | medium | high.")
    summary: str = Field(description="Localized initial-assessment summary.")
    recommendation: str = Field(description="Localized practice recommendation.")
    highlights: list[EvaluationHighlightOut] = Field(description="Per-word highlight statuses.")
    letter_insights: list[LetterInsightOut] = Field(
        description="Per-letter mistakes for this result."
    )
    self_corrections: list[SelfCorrectionOut] = Field(
        default_factory=list,
        description="Self-retry corrections detected inside the evaluated audio.",
    )
    created_at: str = Field(description="ISO-8601 UTC creation timestamp.")
    status: str = Field(
        default="completed", description="queued | processing | completed | failed."
    )


class EvaluationResultResponse(CamelModel):
    result: EvaluationResultOut
