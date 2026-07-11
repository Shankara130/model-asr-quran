from __future__ import annotations

import logging
from collections import defaultdict
from typing import Any

from fastapi import WebSocket

from api.ws.events import build_event

log = logging.getLogger("api.ws.hub")


class RealtimeHub:
    """In-memory registry of live WebSocket connections per session (fan-out only).

    Authoritative session state lives in the DB; this is purely the broadcast
    channel so REST handlers (audio upload, evaluation) can push progress events.
    """

    def __init__(self) -> None:
        self._conns: dict[str, set[WebSocket]] = defaultdict(set)

    async def register(self, session_id: str, ws: WebSocket) -> None:
        self._conns[session_id].add(ws)

    async def unregister(self, session_id: str, ws: WebSocket) -> None:
        conns = self._conns.get(session_id)
        if not conns:
            return
        conns.discard(ws)
        if not conns:
            self._conns.pop(session_id, None)

    async def broadcast(
        self, session_id: str, event_type: str, payload: dict[str, Any] | None = None
    ) -> None:
        envelope = build_event(session_id, event_type, payload)
        for ws in list(self._conns.get(session_id, ())):
            try:
                await ws.send_json(envelope)
            except Exception:  # pragma: no cover - socket dropped
                log.debug("drop on %s/%s", session_id, event_type)

    def connection_count(self, session_id: str) -> int:
        return len(self._conns.get(session_id, ()))


# Module-level singleton used by REST handlers to push progress events.
hub = RealtimeHub()
