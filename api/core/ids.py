from __future__ import annotations

from uuid import uuid4


def _prefixed(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex}"


def new_id(prefix: str) -> str:
    """Generic prefixed id for any row (highlights, chunks, mastery, ...)."""
    return str(uuid4())


def new_request_id() -> str:
    return _prefixed("req")


def new_user_id() -> str:
    return str(uuid4())


def new_session_id() -> str:
    return str(uuid4())


def new_audio_id() -> str:
    return str(uuid4())


def new_upload_id() -> str:
    return _prefixed("upload")


def new_result_id() -> str:
    return str(uuid4())


def new_event_id() -> str:
    return _prefixed("evt")


def new_token_id() -> str:
    return str(uuid4())
