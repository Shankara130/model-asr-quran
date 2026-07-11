from __future__ import annotations

import logging
import sys

from api.core.context import get_request_id, get_user_id


class _ContextFilter(logging.Filter):
    """Attach requestId/userId to every record (never log raw audio bytes)."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = get_request_id()
        record.user_id = get_user_id()
        return True


class _ContextFormatter(logging.Formatter):
    """Defensively defaults request_id/user_id so formatting never KeyErrors."""

    def format(self, record: logging.LogRecord) -> str:
        for attr in ("request_id", "user_id"):
            if not hasattr(record, attr):
                setattr(record, attr, "-")
        return super().format(record)


_FORMAT = "%(asctime)s %(levelname)s [req=%(request_id)s user=%(user_id)s] %(name)s: %(message)s"


def setup_logging() -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(_ContextFormatter(_FORMAT))
    handler.addFilter(_ContextFilter())
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(logging.INFO)
    for noisy in ("sqlalchemy.engine", "aiosqlite", "watchfiles", "uvicorn.access"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
