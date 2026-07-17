from api.schemas.evaluate import EvaluationResultOut


def test_queued_evaluation_allows_pending_result_fields():
    result = EvaluationResultOut(
        result_id="result-id",
        session_id="session-id",
        practice_item_id="item-id",
        match_score=None,
        confidence_level=None,
        summary=None,
        recommendation=None,
        highlights=[],
        letter_insights=[],
        created_at="2026-07-17T00:00:00Z",
        status="queued",
    )

    assert result.status == "queued"
    assert result.match_score is None
