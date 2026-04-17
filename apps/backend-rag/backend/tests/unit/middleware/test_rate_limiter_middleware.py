"""Unit tests for RateLimitMiddleware + _get_rate_limit + in-memory semantics.

Covers the paths not exercised by test_rate_limiter.py (fail-safe only):
  * pattern precedence: exact > prefix > default
  * enforcement once the limit is reached (429 with rate-limit headers)
  * response headers on the happy path
  * in-memory sliding-window: stale entries pruned, remaining counts decrement
  * stale-key eviction when the storage grows past the threshold
  * /health, /docs, /openapi.json are never rate-limited
"""
from __future__ import annotations

import time
from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.middleware.rate_limiter import (
    RateLimiter,
    RateLimitMiddleware,
    _evict_stale_keys,
    _rate_limit_storage,
)


# ---------------------------------------------------------------------------
# _get_rate_limit pattern matching
# ---------------------------------------------------------------------------


@pytest.fixture
def middleware() -> RateLimitMiddleware:
    return RateLimitMiddleware(app=MagicMock())


def test_exact_path_match_wins_over_prefix(middleware: RateLimitMiddleware) -> None:
    """Exact key in RATE_LIMITS beats any prefix match (e.g. /api/agents/)."""
    limit, window = middleware._get_rate_limit("/api/agents/journey/create")
    assert (limit, window) == (10, 3600)


def test_prefix_match_used_when_no_exact(middleware: RateLimitMiddleware) -> None:
    """Unknown path under /api/crm/clients should fall back to its prefix bucket."""
    limit, window = middleware._get_rate_limit("/api/crm/clients/123")
    assert (limit, window) == (100, 60)


def test_default_bucket_when_no_prefix_matches(middleware: RateLimitMiddleware) -> None:
    """Anything outside the configured prefixes falls back to the '*' bucket."""
    limit, window = middleware._get_rate_limit("/totally/unknown/path")
    assert (limit, window) == (200, 60)


# ---------------------------------------------------------------------------
# In-memory sliding window (no Redis)
# ---------------------------------------------------------------------------


def test_in_memory_sliding_window_decrements_remaining() -> None:
    _rate_limit_storage.clear()
    limiter = RateLimiter()
    limiter.redis_available = False
    limiter.redis_client = None

    allowed1, info1 = limiter.is_allowed("k1", limit=3, window=60)
    allowed2, info2 = limiter.is_allowed("k1", limit=3, window=60)
    allowed3, info3 = limiter.is_allowed("k1", limit=3, window=60)
    allowed4, info4 = limiter.is_allowed("k1", limit=3, window=60)

    assert (allowed1, allowed2, allowed3) == (True, True, True)
    assert info1["remaining"] == 2
    assert info2["remaining"] == 1
    assert info3["remaining"] == 0
    assert allowed4 is False  # fourth call exceeds


def test_in_memory_window_prunes_stale_entries() -> None:
    _rate_limit_storage.clear()
    limiter = RateLimiter()
    limiter.redis_available = False
    limiter.redis_client = None

    # Seed with timestamps outside the window (well in the past)
    old = int(time.time()) - 3600
    _rate_limit_storage["k2"] = [old, old, old]

    allowed, info = limiter.is_allowed("k2", limit=3, window=60)
    assert allowed is True
    assert info["remaining"] == 2  # stale entries dropped


def test_evict_stale_keys_above_threshold() -> None:
    """When storage exceeds _MAX_RATE_LIMIT_KEYS, stale-only keys must be dropped."""
    import backend.middleware.rate_limiter as rl

    original_max = rl._MAX_RATE_LIMIT_KEYS
    original_eviction = rl._EVICTION_STALE_SECONDS
    try:
        rl._MAX_RATE_LIMIT_KEYS = 5
        rl._EVICTION_STALE_SECONDS = 60
        rl._rate_limit_storage.clear()

        now = time.time()
        stale = now - 3600
        # 3 stale keys (all timestamps outside the eviction window)
        rl._rate_limit_storage["old1"] = [stale]
        rl._rate_limit_storage["old2"] = [stale]
        rl._rate_limit_storage["old3"] = [stale]
        # 3 fresh keys
        rl._rate_limit_storage["fresh1"] = [now]
        rl._rate_limit_storage["fresh2"] = [now]
        rl._rate_limit_storage["fresh3"] = [now]

        _evict_stale_keys()

        remaining = set(rl._rate_limit_storage.keys())
        assert remaining == {"fresh1", "fresh2", "fresh3"}
    finally:
        rl._MAX_RATE_LIMIT_KEYS = original_max
        rl._EVICTION_STALE_SECONDS = original_eviction


def test_evict_noop_below_threshold() -> None:
    import backend.middleware.rate_limiter as rl

    original_max = rl._MAX_RATE_LIMIT_KEYS
    try:
        rl._MAX_RATE_LIMIT_KEYS = 100
        rl._rate_limit_storage.clear()
        stale = time.time() - 3600
        rl._rate_limit_storage["old1"] = [stale]

        _evict_stale_keys()

        assert "old1" in rl._rate_limit_storage  # not evicted: under threshold
    finally:
        rl._MAX_RATE_LIMIT_KEYS = original_max


# ---------------------------------------------------------------------------
# Middleware dispatch — 429 path + header propagation + skip paths
# ---------------------------------------------------------------------------


def _make_request(
    path: str = "/api/crm/clients",
    *,
    user: object | None = None,
    client_host: str | None = "10.0.0.1",
) -> MagicMock:
    req = MagicMock()
    req.state = MagicMock()
    req.state.user = user

    url = MagicMock()
    url.path = path
    req.url = url

    if client_host is None:
        req.client = None
    else:
        client = MagicMock()
        client.host = client_host
        req.client = client

    return req


@pytest.mark.asyncio
async def test_dispatch_skips_health_path(
    middleware: RateLimitMiddleware, monkeypatch: pytest.MonkeyPatch
) -> None:
    """/health is never rate-limited (and never touches the storage)."""
    limiter_mock = MagicMock()
    limiter_mock.is_allowed = MagicMock()
    monkeypatch.setattr("backend.middleware.rate_limiter.rate_limiter", limiter_mock)

    request = _make_request("/health")
    response = MagicMock(headers={})
    call_next = AsyncMock(return_value=response)

    result = await middleware.dispatch(request, call_next)

    assert result is response
    limiter_mock.is_allowed.assert_not_called()


@pytest.mark.asyncio
async def test_dispatch_allowed_sets_rate_limit_headers(
    middleware: RateLimitMiddleware, monkeypatch: pytest.MonkeyPatch
) -> None:
    limiter_mock = MagicMock()
    limiter_mock.is_allowed = MagicMock(
        return_value=(True, {"limit": 100, "remaining": 42, "reset": 1234567890})
    )
    monkeypatch.setattr("backend.middleware.rate_limiter.rate_limiter", limiter_mock)

    request = _make_request("/api/crm/clients", user={"email": "u@bali.com"})
    response = MagicMock(headers={})
    call_next = AsyncMock(return_value=response)

    result = await middleware.dispatch(request, call_next)

    assert result is response
    assert response.headers["X-RateLimit-Limit"] == "100"
    assert response.headers["X-RateLimit-Remaining"] == "42"
    assert response.headers["X-RateLimit-Reset"] == "1234567890"
    # The key must be user-scoped, not IP-scoped, when user has email
    kwargs_key = limiter_mock.is_allowed.call_args.args[0]
    assert "u@bali.com" in kwargs_key


@pytest.mark.asyncio
async def test_dispatch_denied_returns_429_with_retry_after(
    middleware: RateLimitMiddleware, monkeypatch: pytest.MonkeyPatch
) -> None:
    limiter_mock = MagicMock()
    limiter_mock.is_allowed = MagicMock(
        return_value=(False, {"limit": 10, "remaining": 0, "reset": 1111})
    )
    monkeypatch.setattr("backend.middleware.rate_limiter.rate_limiter", limiter_mock)

    # Path that falls into the (10, 3600) bucket
    request = _make_request("/api/agents/journey/create")
    call_next = AsyncMock()

    response = await middleware.dispatch(request, call_next)

    assert response.status_code == 429
    assert response.headers["X-RateLimit-Limit"] == "10"
    assert response.headers["X-RateLimit-Remaining"] == "0"
    assert response.headers["Retry-After"] == "3600"  # window for this path
    call_next.assert_not_awaited()


@pytest.mark.asyncio
async def test_dispatch_uses_ip_when_no_authenticated_user(
    middleware: RateLimitMiddleware, monkeypatch: pytest.MonkeyPatch
) -> None:
    limiter_mock = MagicMock()
    limiter_mock.is_allowed = MagicMock(
        return_value=(True, {"limit": 100, "remaining": 99, "reset": 1})
    )
    monkeypatch.setattr("backend.middleware.rate_limiter.rate_limiter", limiter_mock)

    request = _make_request("/api/crm/clients", user=None, client_host="203.0.113.5")
    response = MagicMock(headers={})
    await middleware.dispatch(request, AsyncMock(return_value=response))

    kwargs_key = limiter_mock.is_allowed.call_args.args[0]
    assert "203.0.113.5" in kwargs_key


@pytest.mark.asyncio
async def test_dispatch_fails_open_when_limiter_raises(
    middleware: RateLimitMiddleware, monkeypatch: pytest.MonkeyPatch
) -> None:
    """If the limiter itself raises (beyond the internal Redis fallback), the request
    must still flow through — we don't want to 500 every request when rate-limiting
    has an internal bug. This is a hot-path middleware; availability > strictness."""
    limiter_mock = MagicMock()
    limiter_mock.is_allowed = MagicMock(side_effect=RuntimeError("storage exploded"))
    monkeypatch.setattr("backend.middleware.rate_limiter.rate_limiter", limiter_mock)

    request = _make_request("/api/crm/clients", user={"email": "u@bali.com"})
    response = MagicMock(headers={})
    call_next = AsyncMock(return_value=response)

    result = await middleware.dispatch(request, call_next)

    assert result is response
    call_next.assert_awaited_once_with(request)
