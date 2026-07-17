from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from api.db.models import LetterInsight
from api.services import insights_builder


@pytest.mark.asyncio
async def test_weekly_insight_uses_letter_insight_mastery_score(monkeypatch):
    result = SimpleNamespace(
        id="result_1",
        session_id="session_1",
        match_score=88,
        created_at=datetime(2026, 7, 14, tzinfo=timezone.utc),
    )
    letters = [
        LetterInsight(
            id="li_1",
            evaluation_result_id="result_1",
            letter="ب",
            mastery_score=85,
            mistake_count=1,
        ),
        LetterInsight(
            id="li_2",
            evaluation_result_id="result_1",
            letter="ض",
            mastery_score=35,
            mistake_count=4,
        ),
    ]

    calls = 0

    async def results_in_range(*_args):
        nonlocal calls
        calls += 1
        return [result] if calls == 1 else []

    async def letter_insights_for(*_args):
        return letters

    monkeypatch.setattr(insights_builder, "_results_in_range", results_in_range)
    monkeypatch.setattr(insights_builder, "_letter_insights_for", letter_insights_for)

    insight = await insights_builder.build_weekly(object(), "user_1", "2026-07-13")

    assert insight.focus_letter == "ض"
    assert [(item.letter, item.score) for item in insight.letter_mastery] == [
        ("ب", 85),
        ("ض", 35),
    ]
