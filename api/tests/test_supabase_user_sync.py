from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from api.core.errors import ApiError
from api.db.models import User
from api.services.supabase_auth import sync_supabase_user

USER_ID = "11111111-1111-4111-8111-111111111111"
OTHER_ID = "22222222-2222-4222-8222-222222222222"


class SyncSession:
    def __init__(self, *, by_id=None, by_email=None):
        self.by_id = by_id
        self.by_email = by_email
        self.added = []
        self.flush = AsyncMock()
        self.commit = AsyncMock()

    async def get(self, _model, _pk):
        return self.by_id

    async def scalar(self, _statement):
        return self.by_email

    def add(self, value):
        self.added.append(value)


def auth_user(user_id=USER_ID, email="reader@example.test"):
    return {"id": user_id, "email": email, "user_metadata": {"name": "Reader"}}


@pytest.mark.asyncio
async def test_new_supabase_user_creates_profile_with_auth_uuid():
    session = SyncSession()

    user = await sync_supabase_user(session, auth_user())

    assert user.id == USER_ID
    assert user.email == "reader@example.test"
    assert len(session.added) == 2
    session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_existing_supabase_uuid_is_reused():
    existing = User(id=USER_ID, name="Reader", email="reader@example.test")
    session = SyncSession(by_id=existing)

    user = await sync_supabase_user(session, auth_user())

    assert user is existing
    assert user.id == USER_ID
    assert session.added == []


@pytest.mark.asyncio
async def test_email_collision_never_rewrites_existing_primary_key():
    existing = User(id=OTHER_ID, name="Old", email="reader@example.test")
    session = SyncSession(by_email=existing)

    with pytest.raises(ApiError) as exc:
        await sync_supabase_user(session, auth_user())

    assert exc.value.code == "auth_identity_conflict"
    assert existing.id == OTHER_ID
    session.commit.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "payload",
    [
        {"email": "reader@example.test"},
        {"id": "not-a-uuid", "email": "reader@example.test"},
        {"id": USER_ID, "email": ""},
    ],
)
async def test_invalid_supabase_identity_is_rejected(payload):
    session = SyncSession()

    with pytest.raises(ApiError) as exc:
        await sync_supabase_user(session, payload)

    assert exc.value.code == "auth_invalid_credentials"
    session.commit.assert_not_awaited()
