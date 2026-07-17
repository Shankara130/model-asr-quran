from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from api.services import runtime_cleanup


class _Result:
    rowcount = 2


class _Session:
    def __init__(self):
        self.execute = AsyncMock(return_value=_Result())
        self.commit = AsyncMock()


def test_purge_directory_contents_removes_files_and_directories(tmp_path):
    runtime = tmp_path / "runtime"
    nested = runtime / "session"
    nested.mkdir(parents=True)
    (nested / "audio.wav").write_bytes(b"audio")
    (runtime / "chunk.part").write_bytes(b"chunk")

    assert runtime_cleanup.purge_directory_contents(runtime) == 2
    assert runtime.exists()
    assert list(runtime.iterdir()) == []


@pytest.mark.asyncio
async def test_cleanup_updates_interrupted_database_rows(monkeypatch, tmp_path):
    uploads = tmp_path / "uploads"
    audio = tmp_path / "audio"
    uploads.mkdir()
    audio.mkdir()
    (uploads / "orphan").write_bytes(b"chunk")
    (audio / "orphan").write_bytes(b"audio")
    monkeypatch.setattr(runtime_cleanup.settings, "uploads_dir", uploads)
    monkeypatch.setattr(runtime_cleanup.settings, "audio_dir", audio)
    session = _Session()

    result = await runtime_cleanup.cleanup_orphaned_runtime_data(session)

    assert result == {
        "filesystem_entries": 2,
        "uploads": 2,
        "evaluations": 2,
        "sessions": 2,
    }
    assert session.execute.await_count == 3
    session.commit.assert_awaited_once()
