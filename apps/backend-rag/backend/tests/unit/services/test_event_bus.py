"""Tests for EventBus — in-process pub/sub layer."""

import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from backend.services.events.event_bus import EventBus, PG_CHANNEL_MAP


@pytest.fixture
def bus() -> EventBus:
    """Create an EventBus without PG connection (in-process only)."""
    return EventBus(db_dsn="postgresql://test:test@localhost/test", db_pool=None)


class TestEventBusSubscribeEmit:
    """Test in-process pub/sub (no PG connection needed)."""

    @pytest.mark.asyncio
    async def test_subscribe_and_emit(self, bus: EventBus) -> None:
        received: list[dict] = []

        async def handler(payload: dict) -> None:
            received.append(payload)

        bus.subscribe("test.event", handler)
        await bus.emit("test.event", {"key": "value"})

        assert len(received) == 1
        assert received[0]["key"] == "value"

    @pytest.mark.asyncio
    async def test_multiple_handlers(self, bus: EventBus) -> None:
        call_count = 0

        async def handler_a(payload: dict) -> None:
            nonlocal call_count
            call_count += 1

        async def handler_b(payload: dict) -> None:
            nonlocal call_count
            call_count += 1

        bus.subscribe("multi.event", handler_a)
        bus.subscribe("multi.event", handler_b)
        await bus.emit("multi.event", {})

        assert call_count == 2

    @pytest.mark.asyncio
    async def test_no_handlers_no_error(self, bus: EventBus) -> None:
        trace = await bus.emit("nobody.listens", {"data": 1})
        assert trace.handler_count == 0
        assert trace.errors == []

    @pytest.mark.asyncio
    async def test_handler_error_does_not_crash(self, bus: EventBus) -> None:
        async def bad_handler(payload: dict) -> None:
            raise ValueError("boom")

        good_calls: list[dict] = []

        async def good_handler(payload: dict) -> None:
            good_calls.append(payload)

        bus.subscribe("error.event", bad_handler)
        bus.subscribe("error.event", good_handler)

        trace = await bus.emit("error.event", {"test": True})

        # Good handler still ran
        assert len(good_calls) == 1
        # Error was recorded
        assert len(trace.errors) == 1
        assert "boom" in trace.errors[0]

    @pytest.mark.asyncio
    async def test_unsubscribe(self, bus: EventBus) -> None:
        calls = 0

        async def handler(payload: dict) -> None:
            nonlocal calls
            calls += 1

        bus.subscribe("unsub.event", handler)
        await bus.emit("unsub.event", {})
        assert calls == 1

        bus.unsubscribe("unsub.event", handler)
        await bus.emit("unsub.event", {})
        assert calls == 1  # Not called again

    @pytest.mark.asyncio
    async def test_trace_has_timing(self, bus: EventBus) -> None:
        async def slow_handler(payload: dict) -> None:
            await asyncio.sleep(0.01)

        bus.subscribe("timed.event", slow_handler)
        trace = await bus.emit("timed.event", {})

        assert trace.duration_ms >= 5  # At least 5ms
        assert trace.event_type == "timed.event"
        assert trace.source == "in_process"


class TestEventBusStats:
    """Test observability / stats."""

    @pytest.mark.asyncio
    async def test_stats_empty(self, bus: EventBus) -> None:
        stats = bus.get_stats()
        assert stats["running"] is False
        assert stats["total_events"] == 0
        assert stats["total_errors"] == 0

    @pytest.mark.asyncio
    async def test_stats_after_events(self, bus: EventBus) -> None:
        async def noop(payload: dict) -> None:
            pass

        bus.subscribe("stats.event", noop)
        await bus.emit("stats.event", {})
        await bus.emit("stats.event", {})

        stats = bus.get_stats()
        assert stats["event_counts"]["stats.event"] == 2
        assert stats["total_events"] == 2
        assert len(stats["recent_traces"]) == 2


class TestPGChannelMap:
    """Test PG channel configuration."""

    def test_channels_defined(self) -> None:
        assert "practice_changed" in PG_CHANNEL_MAP
        assert "client_changed" in PG_CHANNEL_MAP
        assert "compliance_alert" in PG_CHANNEL_MAP

    def test_event_types_are_dotted(self) -> None:
        for event_type in PG_CHANNEL_MAP.values():
            assert "." in event_type, f"Event type should be dotted: {event_type}"


class TestPGNotificationRouting:
    """Test that PG notifications get routed correctly."""

    @pytest.mark.asyncio
    async def test_pg_event_dispatches_to_handler(self, bus: EventBus) -> None:
        received: list[dict] = []

        async def handler(payload: dict) -> None:
            received.append(payload)

        bus.subscribe("client.changed", handler)

        # Simulate a PG notification
        await bus._handle_pg_event(
            "client_changed",
            '{"client_id": 42, "email": "test@test.com", "operation": "INSERT"}',
        )

        assert len(received) == 1
        assert received[0]["client_id"] == 42
        assert received[0]["_source"] == "pg_notify"
        assert received[0]["_event_type"] == "client.changed"

    @pytest.mark.asyncio
    async def test_invalid_json_does_not_crash(self, bus: EventBus) -> None:
        # Should log warning, not raise
        await bus._handle_pg_event("client_changed", "not json{{{")

    @pytest.mark.asyncio
    async def test_unmapped_channel_logs_warning(self, bus: EventBus) -> None:
        # Unknown channel should be handled gracefully
        await bus._handle_pg_event("unknown_channel", '{"data": 1}')
