"""Per-request context (request id, user id) backed by contextvars.

These are set by middleware / auth dependencies and read by the logging
filter so every log line carries the active request id and user id.
"""

from __future__ import annotations

from contextvars import ContextVar

request_id_var: ContextVar[str] = ContextVar("request_id", default="-")
user_id_var: ContextVar[str] = ContextVar("user_id", default="-")


def set_request_id(value: str) -> None:
    request_id_var.set(value)


def set_user_id(value: str) -> None:
    user_id_var.set(value)


def get_request_id() -> str:
    return request_id_var.get()


def get_user_id() -> str:
    return user_id_var.get()
