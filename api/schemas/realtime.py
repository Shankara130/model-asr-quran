from __future__ import annotations

from typing import Any

from api.schemas.common import CamelModel


class RealtimeEnvelope(CamelModel):
    """Server event envelope (§11.1)."""

    type: str
    session_id: str
    event_id: str
    timestamp: str
    payload: dict[str, Any] = {}
