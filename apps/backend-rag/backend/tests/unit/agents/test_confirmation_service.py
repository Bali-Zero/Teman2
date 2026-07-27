"""
Unit tests for ConfirmationService (VASSAL Phase 3).

Tests the Redis-backed confirmation gate: request, resolve, timeout,
fail-closed, authorization, pub/sub cross-process resolution.

Uses fakeredis (no real Redis). Each test creates a fresh FakeRedis
instance so tests are fully isolated.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any
from unittest.mock import AsyncMock

import fakeredis.aioredis
import pytest

from backend.services.agents.confirmation_service import (
    CONFIRMATION_KEY_PREFIX,
    ConfirmationRedisDown,
    ConfirmationService,
    ConfirmationTimeout,
)

# ─────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────


async def _wait_for_request_id(emitter, timeout: float = 4.0) -> str:
    """Wait until `emitter` has actually been called, then return its request_id.

    These helper tasks used `await asyncio.sleep(0.05)` as a synchronisation
    primitive and then read `emitter.call_args` unconditionally. 50ms is enough
    on an idle machine and not enough on a loaded one: `call_args` is still
    None, the resolver never runs, and the `request_and_wait` under test dies on
    its own 5s timeout with a message about the SERVICE rather than about the
    test's own race. Observed live 2026-07-27 at 98% of a 40-minute suite.

    Wait for the event, do not guess how long it takes.
    """
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout
    while emitter.call_args is None:
        if loop.time() > deadline:
            raise AssertionError(f"emitter was never called within {timeout}s")
        await asyncio.sleep(0.01)
    return emitter.call_args[0][0]["data"]["request_id"]


@pytest.mark.asyncio
async def test_wait_for_request_id_survives_a_late_emit() -> None:
    """Guilt + innocence for the helper that replaced `sleep(0.05)`.

    Guilt: a 200ms emit — four times the old fixed sleep — must still be caught,
    because that is exactly the case the old code got wrong under load. Innocence:
    an emitter that is never called fails fast and says so, instead of leaving the
    caller to die on the service's timeout and blame the service.
    """
    emitter = AsyncMock()

    async def emit_late() -> None:
        await asyncio.sleep(0.2)
        await emitter({"data": {"request_id": "late-42"}})

    task = asyncio.create_task(emit_late())
    assert await _wait_for_request_id(emitter, timeout=4.0) == "late-42"
    await task

    with pytest.raises(AssertionError, match="never called"):
        await _wait_for_request_id(AsyncMock(), timeout=0.05)


class _FakeRedisManager:
    """Minimal RedisManager stand-in backed by fakeredis."""

    def __init__(self, *, available: bool = True) -> None:
        self._client = fakeredis.aioredis.FakeRedis(decode_responses=True)
        self._available = available

    @property
    def available(self) -> bool:
        return self._available

    def get_async_client(self) -> Any | None:
        return self._client if self._available else None


@pytest.fixture
def redis_manager() -> _FakeRedisManager:
    return _FakeRedisManager(available=True)


@pytest.fixture
def service(redis_manager: _FakeRedisManager) -> ConfirmationService:
    return ConfirmationService(redis_manager=redis_manager)


# ─────────────────────────────────────────────────────────────────────────
# Fail-closed when Redis is down
# ─────────────────────────────────────────────────────────────────────────


class TestRedisDown:
    @pytest.mark.asyncio
    async def test_request_raises_when_redis_unavailable(self) -> None:
        rm = _FakeRedisManager(available=False)
        svc = ConfirmationService(redis_manager=rm)
        with pytest.raises(ConfirmationRedisDown):
            await svc.request_and_wait(
                tool_name="image_generation",
                args={"prompt": "test"},
                user_email="damar@balizero.com",
                preview="Generate an image",
            )


# ─────────────────────────────────────────────────────────────────────────
# Approve / Reject paths
# ─────────────────────────────────────────────────────────────────────────


class TestApproveReject:
    @pytest.mark.asyncio
    async def test_approve_path_returns_true(
        self,
        service: ConfirmationService,
    ) -> None:
        """Concurrent resolve(approve) → request_and_wait returns True."""

        async def approve_soon() -> None:
            request_id = await _wait_for_request_id(emitter)
            result = await service.resolve_confirmation(
                request_id=request_id,
                decision="approve",
                user_email="damar@balizero.com",
            )
            assert result is True

        emitter = AsyncMock()
        approve_task = asyncio.create_task(approve_soon())

        approved = await service.request_and_wait(
            tool_name="image_generation",
            args={"prompt": "test"},
            user_email="damar@balizero.com",
            preview="Generate an image",
            emitter=emitter,
            timeout=5.0,
        )
        await approve_task

        assert approved is True
        emitter.assert_called_once()
        event = emitter.call_args[0][0]
        assert event["type"] == "confirmation_required"
        assert event["data"]["tool_name"] == "image_generation"

    @pytest.mark.asyncio
    async def test_reject_path_returns_false(
        self,
        service: ConfirmationService,
    ) -> None:
        """Concurrent resolve(reject) → request_and_wait returns False."""
        emitter = AsyncMock()

        async def reject_soon() -> None:
            request_id = await _wait_for_request_id(emitter)
            await service.resolve_confirmation(
                request_id=request_id,
                decision="reject",
                user_email="damar@balizero.com",
            )

        reject_task = asyncio.create_task(reject_soon())

        approved = await service.request_and_wait(
            tool_name="image_generation",
            args={"prompt": "test"},
            user_email="damar@balizero.com",
            preview="Generate an image",
            emitter=emitter,
            timeout=5.0,
        )
        await reject_task

        assert approved is False


# ─────────────────────────────────────────────────────────────────────────
# Timeout
# ─────────────────────────────────────────────────────────────────────────


class TestTimeout:
    @pytest.mark.asyncio
    async def test_timeout_raises_confirmation_timeout(
        self,
        service: ConfirmationService,
    ) -> None:
        """No resolution within timeout → ConfirmationTimeout."""
        with pytest.raises(ConfirmationTimeout):
            await service.request_and_wait(
                tool_name="image_generation",
                args={"prompt": "test"},
                user_email="damar@balizero.com",
                preview="Generate an image",
                timeout=0.1,  # Fast timeout for test
            )


# ─────────────────────────────────────────────────────────────────────────
# Resolve: unknown / expired / wrong user / invalid decision
# ─────────────────────────────────────────────────────────────────────────


class TestResolveEdgeCases:
    @pytest.mark.asyncio
    async def test_unknown_request_id_returns_false(
        self,
        service: ConfirmationService,
    ) -> None:
        result = await service.resolve_confirmation(
            request_id="nonexistent-uuid",
            decision="approve",
            user_email="damar@balizero.com",
        )
        assert result is False

    @pytest.mark.asyncio
    async def test_wrong_user_email_returns_false(
        self,
        service: ConfirmationService,
        redis_manager: _FakeRedisManager,
    ) -> None:
        """Only the original requester's email may resolve."""
        emitter = AsyncMock()

        async def wrong_user_resolve() -> None:
            request_id = await _wait_for_request_id(emitter)
            # Try to resolve as a different user
            result = await service.resolve_confirmation(
                request_id=request_id,
                decision="approve",
                user_email="hacker@evil.com",
            )
            assert result is False
            # Now resolve correctly so request_and_wait doesn't hang
            await service.resolve_confirmation(
                request_id=request_id,
                decision="reject",
                user_email="damar@balizero.com",
            )

        task = asyncio.create_task(wrong_user_resolve())
        result = await service.request_and_wait(
            tool_name="image_generation",
            args={"prompt": "test"},
            user_email="damar@balizero.com",
            preview="test",
            emitter=emitter,
            timeout=5.0,
        )
        await task
        assert result is False  # reject from the correct user was sent

    @pytest.mark.asyncio
    async def test_invalid_decision_string_returns_false(
        self,
        service: ConfirmationService,
    ) -> None:
        result = await service.resolve_confirmation(
            request_id="anything",
            decision="maybe",
            user_email="damar@balizero.com",
        )
        assert result is False


# ─────────────────────────────────────────────────────────────────────────
# Redis persistence
# ─────────────────────────────────────────────────────────────────────────


class TestRedisPersistence:
    @pytest.mark.asyncio
    async def test_request_persists_under_correct_key(
        self,
        service: ConfirmationService,
        redis_manager: _FakeRedisManager,
    ) -> None:
        """The pending request must be stored in Redis during the wait."""
        emitter = AsyncMock()

        async def check_redis_then_resolve() -> None:
            request_id = await _wait_for_request_id(emitter)
            client = redis_manager.get_async_client()
            raw = await client.get(f"{CONFIRMATION_KEY_PREFIX}{request_id}")
            assert raw is not None
            payload = json.loads(raw)
            assert payload["tool_name"] == "image_generation"
            assert payload["user_email"] == "damar@balizero.com"
            assert payload["preview"] == "test preview"
            # Resolve so the waiter returns
            await service.resolve_confirmation(
                request_id=request_id,
                decision="approve",
                user_email="damar@balizero.com",
            )

        task = asyncio.create_task(check_redis_then_resolve())
        await service.request_and_wait(
            tool_name="image_generation",
            args={"prompt": "test"},
            user_email="damar@balizero.com",
            preview="test preview",
            emitter=emitter,
            timeout=5.0,
        )
        await task


# ─────────────────────────────────────────────────────────────────────────
# SSE emitter callback
# ─────────────────────────────────────────────────────────────────────────


class TestEmitterCallback:
    @pytest.mark.asyncio
    async def test_emitter_receives_correct_sse_event(
        self,
        service: ConfirmationService,
    ) -> None:
        emitter = AsyncMock()

        async def resolve_quickly() -> None:
            request_id = await _wait_for_request_id(emitter)
            await service.resolve_confirmation(
                request_id=request_id,
                decision="approve",
                user_email="damar@balizero.com",
            )

        task = asyncio.create_task(resolve_quickly())
        await service.request_and_wait(
            tool_name="image_generation",
            args={"prompt": "a KITAS card", "style": "photo"},
            user_email="damar@balizero.com",
            preview="About to generate an image (~$0.03)",
            emitter=emitter,
            timeout=5.0,
        )
        await task

        emitter.assert_called_once()
        event = emitter.call_args[0][0]
        assert event["type"] == "confirmation_required"
        data = event["data"]
        assert "request_id" in data
        assert data["tool_name"] == "image_generation"
        assert data["args"] == {"prompt": "a KITAS card", "style": "photo"}
        assert data["preview"] == "About to generate an image (~$0.03)"

    @pytest.mark.asyncio
    async def test_no_emitter_still_works(
        self,
        service: ConfirmationService,
    ) -> None:
        """emitter=None → no SSE event, but request_and_wait still works."""

        async def resolve_quickly() -> None:
            # Without emitter we need another way to get request_id: the single
            # pending key in Redis. Wait for it to appear rather than assuming
            # 50ms is always enough — same race as _wait_for_request_id above.
            client = service._get_client()
            loop = asyncio.get_running_loop()
            deadline = loop.time() + 4.0
            keys: list[str] = []
            while not keys:
                keys = [
                    key
                    async for key in client.scan_iter(match=f"{CONFIRMATION_KEY_PREFIX}*")
                ]
                if keys:
                    break
                if loop.time() > deadline:
                    raise AssertionError("no pending confirmation key appeared within 4.0s")
                await asyncio.sleep(0.01)
            assert len(keys) == 1
            request_id = keys[0].replace(CONFIRMATION_KEY_PREFIX, "")
            await service.resolve_confirmation(
                request_id=request_id,
                decision="approve",
                user_email="damar@balizero.com",
            )

        task = asyncio.create_task(resolve_quickly())
        approved = await service.request_and_wait(
            tool_name="image_generation",
            args={"prompt": "test"},
            user_email="damar@balizero.com",
            preview="test",
            emitter=None,
            timeout=5.0,
        )
        await task
        assert approved is True


# ─────────────────────────────────────────────────────────────────────────
# Pub/sub cross-process resolution
# ─────────────────────────────────────────────────────────────────────────


class TestPubSubCrossProcess:
    @pytest.mark.asyncio
    async def test_pubsub_resolves_local_future(
        self,
        redis_manager: _FakeRedisManager,
    ) -> None:
        """
        Simulate cross-process: the listener receives a pub/sub message
        and resolves the local Future. This tests the pub/sub path even
        when the resolver is in the same process (it publishes AND sets
        the future directly — both paths fire; this test verifies the
        pubsub listener alone would also resolve it).
        """
        service = ConfirmationService(redis_manager=redis_manager)
        # Start the listener
        await service.start()

        emitter = AsyncMock()

        async def resolve_via_pubsub() -> None:
            request_id = await _wait_for_request_id(emitter)
            # Directly publish (simulating a different process calling resolve)
            client = redis_manager.get_async_client()
            await client.publish(
                "conf:resolutions",
                json.dumps({"request_id": request_id, "decision": "approve"}),
            )

        task = asyncio.create_task(resolve_via_pubsub())
        approved = await service.request_and_wait(
            tool_name="image_generation",
            args={"prompt": "test"},
            user_email="damar@balizero.com",
            preview="test",
            emitter=emitter,
            timeout=5.0,
        )
        await task
        await service.stop()
        assert approved is True
