from __future__ import annotations

import pytest

from api.core.errors import ApiError
from api.db.models import EvaluationResult, PracticeSession
from api.routers.evaluate import _load_owned_result
from api.security import CurrentUser
from api.security.deps import require_session_owner


class _Database:
    def __init__(self, rows):
        self.rows = rows

    async def get(self, model, key):
        return self.rows.get((model, key))


def principal(user_id: str) -> CurrentUser:
    return CurrentUser(user_id=user_id, email="redacted", name="User", learning_level="beginner")


@pytest.mark.asyncio
async def test_session_owner_can_access_own_session():
    session = PracticeSession(id="11111111-1111-4111-8111-111111111111", user_id="owner")
    db = _Database({(PracticeSession, session.id): session})

    assert await require_session_owner(session.id, principal("owner"), db) is session


@pytest.mark.asyncio
async def test_foreign_session_is_hidden_as_not_found():
    session = PracticeSession(id="11111111-1111-4111-8111-111111111111", user_id="owner")
    db = _Database({(PracticeSession, session.id): session})

    with pytest.raises(ApiError) as exc:
        await require_session_owner(session.id, principal("attacker"), db)

    assert exc.value.code == "session_not_found"
    assert exc.value.status == 404


@pytest.mark.asyncio
async def test_foreign_evaluation_result_is_hidden_as_not_found():
    session_id = "11111111-1111-4111-8111-111111111111"
    result_id = "22222222-2222-4222-8222-222222222222"
    session = PracticeSession(id=session_id, user_id="owner")
    result = EvaluationResult(id=result_id, session_id=session_id)
    db = _Database(
        {
            (EvaluationResult, result_id): result,
            (PracticeSession, session_id): session,
        }
    )

    with pytest.raises(ApiError) as exc:
        await _load_owned_result(result_id, principal("attacker"), db)

    assert exc.value.code == "session_not_found"
    assert exc.value.status == 404
