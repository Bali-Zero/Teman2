"""Tests for @cache_invalidating decorator.

Covers:
- Success path: all patterns invalidated after the wrapped function returns
- Exception path: no invalidation if wrapped function raises
- Dynamic patterns (callables) resolve with self + args + kwargs
- Redis/cache failure during invalidation does NOT propagate (logger.warning + counter)
- Static-method friendly: works on module-level async functions too
- Multiple calls accumulate counter correctly
"""
from __future__ import annotations

import logging
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from backend.services.common.cache import cache_invalidating


class _FakeService:
    """Minimal class to host decorated methods in tests."""

    def __init__(self, client_id: int = 42) -> None:
        self.client_id = client_id
        self.call_count = 0


# ── 1. Success invalidates every pattern ───────────────────────────────────

@pytest.mark.asyncio
async def test_success_invalidates_all_patterns() -> None:
    calls: list[str] = []

    async def fake_invalidate(pattern: str) -> int:
        calls.append(pattern)
        return 1

    with patch("backend.services.common.cache._invalidate_cache", fake_invalidate):
        @cache_invalidating(["zantara:clients:*", "zantara:stats:*"])
        async def mutate(self: _FakeService) -> str:
            self.call_count += 1
            return "ok"

        svc = _FakeService()
        result = await mutate(svc)

    assert result == "ok"
    assert svc.call_count == 1
    assert calls == ["zantara:clients:*", "zantara:stats:*"]


# ── 2. Exception skips invalidation ────────────────────────────────────────

@pytest.mark.asyncio
async def test_exception_skips_invalidation() -> None:
    calls: list[str] = []

    async def fake_invalidate(pattern: str) -> int:
        calls.append(pattern)
        return 1

    with patch("backend.services.common.cache._invalidate_cache", fake_invalidate):
        @cache_invalidating(["zantara:clients:*"])
        async def mutate(self: _FakeService) -> str:
            raise RuntimeError("boom")

        svc = _FakeService()
        with pytest.raises(RuntimeError, match="boom"):
            await mutate(svc)

    assert calls == [], "invalidation must NOT run when the wrapped function raises"


# ── 3. Callable pattern resolves with self + kwargs ────────────────────────

@pytest.mark.asyncio
async def test_callable_pattern_receives_self_and_kwargs() -> None:
    calls: list[str] = []

    async def fake_invalidate(pattern: str) -> int:
        calls.append(pattern)
        return 1

    with patch("backend.services.common.cache._invalidate_cache", fake_invalidate):
        @cache_invalidating([
            lambda self, client_id, **_: f"zantara:crm_client:{client_id}:*",
            "zantara:crm_clients_stats:*",
        ])
        async def update_client(self: _FakeService, client_id: int, **payload: Any) -> dict[str, Any]:
            return {"id": client_id, **payload}

        svc = _FakeService()
        out = await update_client(svc, 7, name="Zero", email="z@balizero.com")

    assert out == {"id": 7, "name": "Zero", "email": "z@balizero.com"}
    assert calls == ["zantara:crm_client:7:*", "zantara:crm_clients_stats:*"]


# ── 4. Positional-only callable pattern ────────────────────────────────────

@pytest.mark.asyncio
async def test_callable_pattern_with_positional_args() -> None:
    calls: list[str] = []

    async def fake_invalidate(pattern: str) -> int:
        calls.append(pattern)
        return 1

    with patch("backend.services.common.cache._invalidate_cache", fake_invalidate):
        @cache_invalidating([
            lambda self, practice_id, new_status: f"zantara:practice:{practice_id}:*",
        ])
        async def update_practice_status(
            self: _FakeService, practice_id: int, new_status: str,
        ) -> bool:
            return True

        svc = _FakeService()
        await update_practice_status(svc, 99, "completed")

    assert calls == ["zantara:practice:99:*"]


# ── 5. Invalidation failure must not propagate ─────────────────────────────

@pytest.mark.asyncio
async def test_invalidation_failure_swallowed(caplog: pytest.LogCaptureFixture) -> None:
    async def fake_invalidate(pattern: str) -> int:
        raise ConnectionError("redis down")

    with patch("backend.services.common.cache._invalidate_cache", fake_invalidate):
        @cache_invalidating(["zantara:clients:*"])
        async def mutate(self: _FakeService) -> str:
            return "ok"

        svc = _FakeService()
        with caplog.at_level(logging.WARNING, logger="backend.services.common.cache"):
            result = await mutate(svc)

    assert result == "ok", "wrapped call must still succeed if invalidation fails"
    warning_msgs = [r.message for r in caplog.records if r.levelno == logging.WARNING]
    assert any("redis down" in m or "cache invalidation" in m.lower() for m in warning_msgs)


# ── 6. Works on module-level async functions (no self) ─────────────────────

@pytest.mark.asyncio
async def test_decorator_on_module_level_function() -> None:
    calls: list[str] = []

    async def fake_invalidate(pattern: str) -> int:
        calls.append(pattern)
        return 1

    with patch("backend.services.common.cache._invalidate_cache", fake_invalidate):
        @cache_invalidating(["zantara:news:*"])
        async def free_function(x: int) -> int:
            return x + 1

        out = await free_function(41)

    assert out == 42
    assert calls == ["zantara:news:*"]


# ── 7. Multiple invocations accumulate metrics counter ─────────────────────

@pytest.mark.asyncio
async def test_success_metrics_counter_increment() -> None:
    async def fake_invalidate(pattern: str) -> int:
        return 3

    success_counter = MagicMock()
    error_counter = MagicMock()

    with (
        patch("backend.services.common.cache._invalidate_cache", fake_invalidate),
        patch("backend.services.common.cache._inc_success_counter", success_counter),
        patch("backend.services.common.cache._inc_error_counter", error_counter),
    ):
        @cache_invalidating(["zantara:a:*", "zantara:b:*"])
        async def mutate(self: _FakeService) -> None:
            return None

        svc = _FakeService()
        await mutate(svc)
        await mutate(svc)

    # 2 calls × 2 patterns = 4 success increments, 0 errors
    assert success_counter.call_count == 4
    assert error_counter.call_count == 0


@pytest.mark.asyncio
async def test_error_metrics_counter_increment() -> None:
    async def fake_invalidate(pattern: str) -> int:
        raise ConnectionError("redis down")

    success_counter = MagicMock()
    error_counter = MagicMock()

    with (
        patch("backend.services.common.cache._invalidate_cache", fake_invalidate),
        patch("backend.services.common.cache._inc_success_counter", success_counter),
        patch("backend.services.common.cache._inc_error_counter", error_counter),
    ):
        @cache_invalidating(["zantara:x:*"])
        async def mutate(self: _FakeService) -> None:
            return None

        svc = _FakeService()
        await mutate(svc)

    assert success_counter.call_count == 0
    assert error_counter.call_count == 1
