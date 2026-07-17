from __future__ import annotations

import pytest

from api.core.rate_limit import Limit, SlidingWindowLimiter, classify_request


def test_classify_sensitive_post_endpoints():
    assert classify_request("POST", "/v1/auth/login")[0] == "auth"
    assert classify_request("POST", "/v1/practice-sessions/id/audio")[0] == "upload"
    chunk_rule = classify_request("POST", "/v1/practice-sessions/id/audio/chunks/u/complete")
    assert chunk_rule[0] == "upload"
    assert classify_request("POST", "/v1/practice-sessions/id/evaluate")[0] == "evaluate"
    assert classify_request("GET", "/v1/practice-sessions/id/evaluate") is None


@pytest.mark.asyncio
async def test_sliding_window_rejects_requests_over_limit():
    limiter = SlidingWindowLimiter()
    limit = Limit(requests=2, window_seconds=60)

    assert await limiter.allow("auth", "127.0.0.1", limit) == (True, 0)
    assert await limiter.allow("auth", "127.0.0.1", limit) == (True, 0)
    allowed, retry_after = await limiter.allow("auth", "127.0.0.1", limit)

    assert allowed is False
    assert retry_after > 0


@pytest.mark.asyncio
async def test_rate_limit_isolated_by_group_and_identity():
    limiter = SlidingWindowLimiter()
    limit = Limit(requests=1, window_seconds=60)

    assert await limiter.allow("auth", "ip-a", limit) == (True, 0)
    assert await limiter.allow("upload", "ip-a", limit) == (True, 0)
    assert await limiter.allow("auth", "ip-b", limit) == (True, 0)
