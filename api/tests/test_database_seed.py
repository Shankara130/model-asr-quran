from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from api import app
from api.services.seed_data import seed_practice_items


class _Rows:
    def __init__(self, ids: set[str]):
        self.ids = ids

    def all(self):
        return [(item_id,) for item_id in self.ids]


class SeedSession:
    def __init__(self):
        self.ids: set[str] = set()
        self.pending: list[str] = []

    async def execute(self, _statement):
        return _Rows(self.ids)

    def add(self, item):
        self.pending.append(item.id)

    async def commit(self):
        self.ids.update(self.pending)
        self.pending.clear()


@pytest.mark.asyncio
async def test_practice_seed_is_idempotent():
    session = SeedSession()

    first_added = await seed_practice_items(session)
    first_total = len(session.ids)
    second_added = await seed_practice_items(session)

    assert first_added == first_total
    assert first_total > 0
    assert second_added == 0
    assert len(session.ids) == first_total


@pytest.mark.asyncio
async def test_startup_skips_dev_user_when_supabase_auth_is_enabled(monkeypatch):
    dev_seed = AsyncMock()
    practice_seed = AsyncMock()
    cleanup = AsyncMock(return_value={})
    monkeypatch.setattr(app, "supabase_auth_enabled", lambda: True)
    monkeypatch.setattr(app, "seed_dev_user", dev_seed)
    monkeypatch.setattr(app, "seed_practice_items", practice_seed)
    monkeypatch.setattr(app, "cleanup_orphaned_runtime_data", cleanup)

    await app.seed_startup_data(object())

    dev_seed.assert_not_awaited()
    practice_seed.assert_awaited_once()
    cleanup.assert_awaited_once()
