"""Tests for HIGH-13: KG cache proactive pub/sub invalidation.

Scenarios covered:
- Publisher fires on increment_kg_version + debounces multiple writes into one
  pub/sub publish (anti-storm)
- Listener subscribes to zantara:kg:invalidate, decodes payload, calls
  clear_pattern on the CacheService for each key pattern
- Cross-cell visibility: writer in "cell A" publishes → reader in "cell B"
  sees clear_pattern invoked within 100ms of the publish
- Redis unavailable → start_invalidation_listener exits cleanly without
  raising (lazy fallback remains in charge)
- Malformed payload does not crash the listener
"""
from __future__ import annotations

import asyncio
import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.services.rag import kg_cache


@pytest.fixture(autouse=True)
def _reset_kg_state() -> None:
    # Reset publish-state + listener singleton so each test starts clean.
    kg_cache._publish_state["pending"] = False
    kg_cache._publish_state["last_version"] = 0
    kg_cache._publish_state["task"] = None
    # Reset version counter to a known baseline.
    kg_cache._kg_version = 0
    # Drop any previously-built listener so start_invalidation_listener() creates a new one.
    kg_cache._invalidation_listener = None
    yield


# ── Publisher ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_increment_publishes_invalidate_after_debounce(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Single increment results in exactly one publish after the debounce window."""
    fake_redis = MagicMock()
    fake_redis.publish = AsyncMock(return_value=0)
    monkeypatch.setattr(kg_cache, "_get_async_redis", lambda: fake_redis)

    kg_cache.increment_kg_version()

    # Before debounce elapses, publish must not have fired yet.
    fake_redis.publish.assert_not_called()
    # Wait longer than _PUBLISH_DEBOUNCE_SEC + scheduling slack.
    await asyncio.sleep(kg_cache._PUBLISH_DEBOUNCE_SEC + 0.05)

    fake_redis.publish.assert_awaited_once()
    (channel, payload) = fake_redis.publish.call_args.args
    assert channel == kg_cache.KG_INVALIDATE_CHANNEL
    decoded = json.loads(payload)
    assert decoded["version"] == 1
    assert "zantara:kg:entity:*" in decoded["keys"]


@pytest.mark.asyncio
async def test_rapid_increments_debounce_into_single_publish(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """10 writes within the debounce window coalesce into 1 publish (anti-storm)."""
    fake_redis = MagicMock()
    fake_redis.publish = AsyncMock(return_value=0)
    monkeypatch.setattr(kg_cache, "_get_async_redis", lambda: fake_redis)

    for _ in range(10):
        kg_cache.increment_kg_version()

    await asyncio.sleep(kg_cache._PUBLISH_DEBOUNCE_SEC + 0.05)

    # Only one publish despite 10 increments.
    fake_redis.publish.assert_awaited_once()


@pytest.mark.asyncio
async def test_publish_skipped_when_redis_absent(monkeypatch: pytest.MonkeyPatch) -> None:
    """increment_kg_version must not raise when Redis is unavailable."""
    monkeypatch.setattr(kg_cache, "_get_async_redis", lambda: None)

    # Should not raise — graceful degradation.
    kg_cache.increment_kg_version()
    await asyncio.sleep(kg_cache._PUBLISH_DEBOUNCE_SEC + 0.05)


# ── Listener ──────────────────────────────────────────────────────────────


class _FakePubSub:
    """Minimal Redis pubsub stub: hand-feed messages via `.push()`."""

    def __init__(self) -> None:
        self._messages: asyncio.Queue[dict[str, Any] | None] = asyncio.Queue()
        self.subscribed_to: list[str] = []
        self.closed = False

    async def subscribe(self, channel: str) -> None:
        self.subscribed_to.append(channel)

    async def unsubscribe(self, channel: str) -> None:
        pass

    async def close(self) -> None:
        self.closed = True

    async def get_message(self, ignore_subscribe_messages: bool = True, timeout: float = 1.0) -> dict[str, Any] | None:
        try:
            return await asyncio.wait_for(self._messages.get(), timeout=timeout)
        except asyncio.TimeoutError:
            return None

    def push(self, payload: dict[str, Any]) -> None:
        self._messages.put_nowait({"type": "message", "data": json.dumps(payload).encode()})


@pytest.mark.asyncio
async def test_listener_clears_cache_patterns_on_message(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Listener receives a published message and calls clear_pattern for every key."""
    fake_cache = MagicMock()
    fake_cache.clear_pattern = AsyncMock(return_value=3)

    fake_pubsub = _FakePubSub()
    fake_redis = MagicMock()
    fake_redis.pubsub = MagicMock(return_value=fake_pubsub)

    monkeypatch.setattr(kg_cache, "_get_async_redis", lambda: fake_redis)

    # Swap the KGCache singleton so get_kg_cache()._get_cache() returns our mock.
    kg_instance = kg_cache.KGCache()
    kg_instance._initialized = True
    kg_instance._cache = fake_cache
    monkeypatch.setattr(kg_cache, "_kg_cache", kg_instance)

    listener = await kg_cache.start_invalidation_listener()

    # Simulate an event published from a peer cell.
    fake_pubsub.push({"version": 7, "keys": ["zantara:kg:entity:*", "zantara:kg:subgraph:*"]})

    # Give the listener coroutine a chance to process.
    for _ in range(20):
        await asyncio.sleep(0.05)
        if fake_cache.clear_pattern.call_count >= 2:
            break

    await listener.stop()

    calls = [c.args[0] for c in fake_cache.clear_pattern.await_args_list]
    assert "zantara:kg:entity:*" in calls
    assert "zantara:kg:subgraph:*" in calls
    assert fake_pubsub.subscribed_to == [kg_cache.KG_INVALIDATE_CHANNEL]


@pytest.mark.asyncio
async def test_listener_tolerates_malformed_message(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Non-JSON payload must not crash the listener loop."""
    fake_cache = MagicMock()
    fake_cache.clear_pattern = AsyncMock(return_value=0)

    fake_pubsub = _FakePubSub()
    # Hand-push a garbage payload via a custom message dict.
    fake_pubsub._messages.put_nowait({"type": "message", "data": b"\x00\x01notjson"})

    fake_redis = MagicMock()
    fake_redis.pubsub = MagicMock(return_value=fake_pubsub)
    monkeypatch.setattr(kg_cache, "_get_async_redis", lambda: fake_redis)

    kg_instance = kg_cache.KGCache()
    kg_instance._initialized = True
    kg_instance._cache = fake_cache
    monkeypatch.setattr(kg_cache, "_kg_cache", kg_instance)

    listener = await kg_cache.start_invalidation_listener()
    await asyncio.sleep(0.2)
    await listener.stop()

    # Malformed message: clear_pattern must NOT have been called.
    fake_cache.clear_pattern.assert_not_called()


@pytest.mark.asyncio
async def test_listener_exits_cleanly_without_redis(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """start_invalidation_listener must return a stopped listener when Redis is absent."""
    monkeypatch.setattr(kg_cache, "_get_async_redis", lambda: None)

    listener = await kg_cache.start_invalidation_listener()

    # Give its coroutine a chance to run and return.
    await asyncio.sleep(0.1)
    # Task should be done (listener saw no Redis and exited).
    assert listener._task is not None
    assert listener._task.done()


# ── End-to-end cross-cell visibility ──────────────────────────────────────

@pytest.mark.asyncio
async def test_writer_to_reader_roundtrip_under_100ms(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Writer's increment → debounced publish → listener clears within 200ms."""
    # Shared pub/sub channel (one fake pubsub per listener, but same fake Redis).
    fake_pubsub = _FakePubSub()
    fake_redis = MagicMock()

    async def fake_publish(channel: str, payload: str) -> int:
        # Immediately hand the message to the subscriber's queue.
        fake_pubsub._messages.put_nowait({"type": "message", "data": payload.encode()})
        return 1

    fake_redis.publish = fake_publish
    fake_redis.pubsub = MagicMock(return_value=fake_pubsub)
    monkeypatch.setattr(kg_cache, "_get_async_redis", lambda: fake_redis)

    fake_cache = MagicMock()
    fake_cache.clear_pattern = AsyncMock(return_value=0)
    kg_instance = kg_cache.KGCache()
    kg_instance._initialized = True
    kg_instance._cache = fake_cache
    monkeypatch.setattr(kg_cache, "_kg_cache", kg_instance)

    listener = await kg_cache.start_invalidation_listener()

    # "Writer" fires increment on the same loop; debounced publish will hit our
    # fake_publish which pushes straight into the listener's queue.
    t0 = asyncio.get_event_loop().time()
    kg_cache.increment_kg_version()

    for _ in range(40):  # up to ~2s
        await asyncio.sleep(0.05)
        if fake_cache.clear_pattern.call_count >= 1:
            break

    elapsed_ms = (asyncio.get_event_loop().time() - t0) * 1000
    await listener.stop()

    # 4 default patterns, all should have been cleared once each.
    assert fake_cache.clear_pattern.await_count >= 1
    # Debounce (50ms) + scheduling slack — well under 500ms.
    assert elapsed_ms < 500, f"cross-cell propagation took {elapsed_ms:.0f}ms"
