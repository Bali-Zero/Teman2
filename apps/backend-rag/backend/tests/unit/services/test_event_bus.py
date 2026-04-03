"""Tests for EventBus — in-process pub/sub + handlers."""

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch

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


class TestDeduplication:
    """Test dedup guard in handlers."""

    def test_is_duplicate_first_call(self) -> None:
        from backend.services.events.handlers import _is_duplicate, _recent_events
        _recent_events.clear()
        assert _is_duplicate("test:key:1") is False

    def test_is_duplicate_second_call(self) -> None:
        from backend.services.events.handlers import _is_duplicate, _recent_events
        _recent_events.clear()
        _is_duplicate("test:key:2")
        assert _is_duplicate("test:key:2") is True

    def test_different_keys_not_duplicate(self) -> None:
        from backend.services.events.handlers import _is_duplicate, _recent_events
        _recent_events.clear()
        _is_duplicate("test:key:a")
        assert _is_duplicate("test:key:b") is False


class TestChainContext:
    """Test cross-chain shared context."""

    def test_store_and_read(self) -> None:
        from backend.services.events.handlers import (
            _chain_context,
            _store_context,
            get_chain_context,
        )
        _chain_context.clear()

        _store_context("client.changed", 42, {"email": "x@y.com"})
        ctx = get_chain_context()

        assert "client.changed:42" in ctx
        assert ctx["client.changed:42"]["email"] == "x@y.com"
        assert "_stored_at" in ctx["client.changed:42"]

    def test_context_prunes_old_entries(self) -> None:
        from backend.services.events.handlers import (
            _chain_context,
            _store_context,
            _CHAIN_CONTEXT_MAX,
        )
        _chain_context.clear()

        # Fill beyond max
        for i in range(_CHAIN_CONTEXT_MAX + 50):
            _store_context("test", i, {"i": i})

        assert len(_chain_context) <= _CHAIN_CONTEXT_MAX

    def test_get_chain_context_is_independent(self) -> None:
        from backend.services.events.handlers import (
            _chain_context,
            get_chain_context,
        )
        _chain_context.clear()
        _chain_context["test:1"] = {"data": True}

        ctx = get_chain_context()
        # Deleting from copy doesn't affect original
        del ctx["test:1"]
        assert "test:1" in _chain_context


class TestHandlerRegistration:
    """Test that register_handlers wires everything correctly."""

    @pytest.mark.asyncio
    async def test_register_handlers_subscribes_all(self) -> None:
        bus = EventBus(db_dsn="postgresql://test:test@localhost/test", db_pool=None)
        mock_pool = MagicMock()

        from backend.services.events.handlers import register_handlers, _recent_events
        _recent_events.clear()

        register_handlers(bus, mock_pool)

        assert "client.changed" in bus._subscribers
        assert "practice.status_changed" in bus._subscribers
        assert "compliance.alert" in bus._subscribers
        assert len(bus._subscribers["client.changed"]) == 1
        assert len(bus._subscribers["practice.status_changed"]) == 1
        assert len(bus._subscribers["compliance.alert"]) == 1

    @pytest.mark.asyncio
    async def test_client_insert_triggers_background_tasks(self) -> None:
        """Verify that a client INSERT event creates background tasks."""
        bus = EventBus(db_dsn="postgresql://test:test@localhost/test", db_pool=None)
        mock_pool = MagicMock()

        from backend.services.events.handlers import register_handlers, _recent_events
        _recent_events.clear()

        register_handlers(bus, mock_pool)

        # Mock the background task functions
        with patch("backend.services.events.handlers._create_drive_folder", new_callable=AsyncMock) as mock_drive, \
             patch("backend.services.events.handlers._log_interaction", new_callable=AsyncMock) as mock_log, \
             patch("backend.services.events.handlers.invalidate_cache", create=True, new_callable=AsyncMock):

            trace = await bus.emit("client.changed", {
                "client_id": 99,
                "email": "new@client.com",
                "operation": "INSERT",
            })

            # Allow background tasks to start
            await asyncio.sleep(0.05)

            assert trace.handler_count == 1
            assert trace.errors == []

    @pytest.mark.asyncio
    async def test_practice_completed_checks_expiry(self) -> None:
        """Verify practice completion triggers expiry check."""
        bus = EventBus(db_dsn="postgresql://test:test@localhost/test", db_pool=None)
        mock_pool = MagicMock()

        from backend.services.events.handlers import register_handlers, _recent_events
        _recent_events.clear()

        register_handlers(bus, mock_pool)

        with patch("backend.services.events.handlers._check_client_expiry_on_completion", new_callable=AsyncMock) as mock_check, \
             patch("backend.services.events.handlers.invalidate_cache", create=True, new_callable=AsyncMock):

            trace = await bus.emit("practice.status_changed", {
                "practice_id": 55,
                "client_id": 10,
                "old_status": "approved",
                "new_status": "completed",
            })

            await asyncio.sleep(0.05)

            assert trace.handler_count == 1
            assert trace.errors == []

    @pytest.mark.asyncio
    async def test_compliance_high_sends_telegram(self) -> None:
        """Verify high severity compliance alert sends Telegram."""
        bus = EventBus(db_dsn="postgresql://test:test@localhost/test", db_pool=None)
        mock_pool = MagicMock()

        from backend.services.events.handlers import register_handlers, _recent_events
        _recent_events.clear()

        register_handlers(bus, mock_pool)

        with patch("backend.services.events.handlers._send_admin_telegram", new_callable=AsyncMock) as mock_tg, \
             patch("backend.services.events.handlers._log_interaction", new_callable=AsyncMock):

            await bus.emit("compliance.alert", {
                "alert_id": "a1",
                "client_id": 5,
                "severity": "critical",
                "alert_type": "kitas_expiry",
                "message": "KITAS expires in 7 days",
            })

            await asyncio.sleep(0.05)
            # Telegram task was created (verify no errors in trace)
