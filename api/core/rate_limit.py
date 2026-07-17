from __future__ import annotations

import asyncio
import time
from collections import defaultdict, deque
from dataclasses import dataclass

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

from api.core.middleware import make_error_response
from api.settings import settings


@dataclass(frozen=True)
class Limit:
    requests: int
    window_seconds: int = 60


class SlidingWindowLimiter:
    def __init__(self) -> None:
        self._events: dict[tuple[str, str], deque[float]] = defaultdict(deque)
        self._lock = asyncio.Lock()

    async def allow(self, group: str, identity: str, limit: Limit) -> tuple[bool, int]:
        now = time.monotonic()
        cutoff = now - limit.window_seconds
        key = (group, identity)
        async with self._lock:
            events = self._events[key]
            while events and events[0] <= cutoff:
                events.popleft()
            if len(events) >= limit.requests:
                retry_after = max(1, int(events[0] + limit.window_seconds - now) + 1)
                return False, retry_after
            events.append(now)
            return True, 0


def classify_request(method: str, path: str) -> tuple[str, Limit] | None:
    if method != "POST":
        return None
    if path in {"/v1/auth/login", "/v1/auth/signup", "/v1/auth/refresh"}:
        return "auth", Limit(settings.rate_limit_auth_per_minute)
    if path.startswith("/v1/practice-sessions/") and (
        path.endswith("/audio") or "/audio/chunks/" in path
    ):
        return "upload", Limit(settings.rate_limit_upload_per_minute)
    if path.startswith("/v1/practice-sessions/") and (
        path.endswith("/evaluate") or path.endswith("/evaluate/retry")
    ):
        return "evaluate", Limit(settings.rate_limit_evaluate_per_minute)
    return None


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app) -> None:
        super().__init__(app)
        self._limiter = SlidingWindowLimiter()

    async def dispatch(self, request: Request, call_next):
        rule = classify_request(request.method, request.url.path)
        if rule is None:
            return await call_next(request)

        group, limit = rule
        identity = request.client.host if request.client else "unknown"
        allowed, retry_after = await self._limiter.allow(group, identity, limit)
        if allowed:
            return await call_next(request)

        response = make_error_response(
            request,
            "rate_limited",
            "Terlalu banyak permintaan. Silakan coba lagi.",
        )
        response.headers["Retry-After"] = str(retry_after)
        return response
