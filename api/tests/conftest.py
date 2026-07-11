"""Shared fixtures.

Isolate the backend from the real dev DB by pointing settings at a temp dir
BEFORE any api.* module is imported (settings is parsed at import time).
"""

from __future__ import annotations

import os
import tempfile

_tmp = tempfile.mkdtemp(prefix="sobat-api-test-")
os.environ.setdefault("SOBAT_DATABASE_URL", f"sqlite+aiosqlite:///{_tmp}/test.db")
os.environ.setdefault("SOBAT_UPLOADS_DIR", f"{_tmp}/uploads")
os.environ.setdefault("SOBAT_AUDIO_DIR", f"{_tmp}/audio")

import pytest  # noqa: E402
from starlette.testclient import TestClient  # noqa: E402


@pytest.fixture(scope="session")
def client():
    from api.app import create_app

    with TestClient(create_app()) as c:
        yield c


@pytest.fixture(scope="session")
def auth_token(client: TestClient) -> str:
    r = client.post("/v1/auth/login", json={"email": "alya@sobat.ngaji", "password": "anything"})
    assert r.status_code == 200
    return r.json()["tokens"]["accessToken"]


@pytest.fixture()
def auth_headers(auth_token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {auth_token}"}
