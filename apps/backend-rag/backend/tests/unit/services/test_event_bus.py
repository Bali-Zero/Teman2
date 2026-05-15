"""Tests for EventBus — in-process pub/sub + handlers."""

import asyncio
import json
import os
from unittest.mock import AsyncMock, MagicMock, patch

try:
    import asyncpg
except ImportError:  # pragma: no cover
    asyncpg = None  # type: ignore[assignment]

import pytest

from backend.services.events.event_bus import PG_CHANNEL_MAP, EventBus

TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL")


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
        assert "intel_event" in PG_CHANNEL_MAP
        assert "lkpm_ingest_completed" in PG_CHANNEL_MAP
        assert PG_CHANNEL_MAP["whatsapp_message_received"] == "whatsapp.message_received"

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

    @pytest.mark.asyncio
    async def test_pg_compliance_alert_reaches_registered_handlers(self) -> None:
        """PG ``compliance_alert`` channel must reach handlers registered on
        the dotted event type ``compliance.alert`` and trigger cache
        invalidation. Regression for the channel/event-type mismatch where
        compliance handlers were keyed on ``compliance_alert_created`` and
        therefore never fired from PG NOTIFY.
        """
        bus = EventBus(db_dsn="postgresql://test:test@localhost/test", db_pool=None)
        mock_pool = MagicMock()

        from backend.services.events.handlers import _recent_events, register_handlers

        _recent_events.clear()
        register_handlers(bus, mock_pool)

        with patch(
            "backend.core.cache.invalidate_cache",
            new_callable=AsyncMock,
        ) as mock_invalidate:
            await bus._handle_pg_event(
                "compliance_alert",
                json.dumps(
                    {
                        "alert_id": "a1",
                        "client_id": 5,
                        "severity": "warning",
                        "alert_type": "kitas_expiry",
                        "message": "KITAS expires soon",
                    }
                ),
            )

            mock_invalidate.assert_any_await("zantara:compliance_alerts:5:*")
            mock_invalidate.assert_any_await("zantara:compliance_metrics:*")


class TestRealPGNotificationRouting:
    """Integration-style EventBus routing through a real PostgreSQL NOTIFY.

    Skipped unless ``TEST_DATABASE_URL`` is set and ``asyncpg`` is installed.
    Locally: ``TEST_DATABASE_URL=postgresql:///postgres pytest ...``.
    """

    @pytest.mark.skipif(
        asyncpg is None or not TEST_DATABASE_URL,
        reason="TEST_DATABASE_URL not set or asyncpg missing",
    )
    @pytest.mark.asyncio
    async def test_real_notify_dispatches_to_compliance_handler(self) -> None:
        assert asyncpg is not None
        assert TEST_DATABASE_URL is not None

        received: list[dict[str, object]] = []
        done = asyncio.Event()

        async def handler(payload: dict[str, object]) -> None:
            received.append(payload)
            done.set()

        bus = EventBus(db_dsn=TEST_DATABASE_URL, db_pool=None)
        bus.subscribe("compliance.alert", handler)

        notify_conn = None
        try:
            await bus.start()
            for _ in range(30):
                if bus._conn is not None:
                    break
                await asyncio.sleep(0.1)
            else:
                pytest.fail("EventBus did not open a PostgreSQL listener")

            await asyncio.sleep(0.2)
            notify_conn = await asyncpg.connect(TEST_DATABASE_URL)
            await notify_conn.execute(
                "SELECT pg_notify($1, $2)",
                "compliance_alert",
                json.dumps(
                    {
                        "alert_id": "real-notify-test",
                        "client_id": 42,
                        "severity": "critical",
                    }
                ),
            )

            await asyncio.wait_for(done.wait(), timeout=3.0)
        finally:
            if notify_conn is not None:
                await notify_conn.close()
            await bus.stop()

        assert received
        assert received[0]["_source"] == "pg_notify"
        assert received[0]["_channel"] == "compliance_alert"
        assert received[0]["_event_type"] == "compliance.alert"
        assert received[0]["client_id"] == 42


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
            _CHAIN_CONTEXT_MAX,
            _chain_context,
            _store_context,
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

        from backend.services.events.handlers import _recent_events, register_handlers
        _recent_events.clear()

        register_handlers(bus, mock_pool)

        assert "client.changed" in bus._subscribers
        assert "practice.status_changed" in bus._subscribers
        assert "compliance.alert" in bus._subscribers
        assert len(bus._subscribers["client.changed"]) == 1
        # practice.status_changed has TWO subscribers: the core handler in
        # handlers/_core.py (invalidates cache + checks client expiry) AND
        # the partners module's handle_practice_status_changed (added by
        # crm/partners/events.py::register_partner_handlers, wired in at
        # the end of core.register_handlers). Before the handlers.py →
        # handlers/_core.py move, register_handlers was silently unreachable
        # (package shadowed module), so this test never exercised the real
        # subscription count and the 1-subscriber expectation went stale.
        assert len(bus._subscribers["practice.status_changed"]) == 2
        # 2 subscribers on compliance.alert: the core handler in handlers/_core.py
        # (Telegram + outbox fanout) AND the cache-invalidation handler from
        # compliance_handlers.HANDLERS (registered after the core wiring via
        # compliance_handlers.HANDLERS).
        assert len(bus._subscribers["compliance.alert"]) == 2
        assert "intel.event" in bus._subscribers
        assert "lkpm.ingest_completed" in bus._subscribers
        assert "whatsapp.message_received" in bus._subscribers

    @pytest.mark.asyncio
    async def test_whatsapp_message_received_logs_crm_interaction(self) -> None:
        """Matched wa-mirror messages should enter the CRM interaction timeline."""
        bus = EventBus(db_dsn="postgresql://test:test@localhost/test", db_pool=None)

        conn = MagicMock()
        conn.fetchrow = AsyncMock(
            side_effect=[
                {
                    "id": 26650,
                    "client_id": 42,
                    "practice_id": 88,
                    "direction": "inbound",
                    "body": "Can you help with my KITAS renewal?",
                    "message_text": "Can you help with my KITAS renewal?",
                    "message_date": "2026-05-15T02:48:33+00:00",
                    "team_member_email": "adit@balizero.com",
                    "team_member_phone": "+628111111111",
                    "counterpart_phone": "+628222222222",
                    "media_type": "text",
                    "media_stored_path": None,
                },
                None,
            ]
        )
        conn.execute = AsyncMock(return_value="INSERT 0 1")

        class _Acquire:
            async def __aenter__(self) -> MagicMock:
                return conn

            async def __aexit__(self, *_args: object) -> None:
                return None

        class _Pool:
            def acquire(self) -> _Acquire:
                return _Acquire()

        from backend.services.events.handlers import _recent_events, register_handlers

        _recent_events.clear()
        register_handlers(bus, _Pool())  # type: ignore[arg-type]

        trace = await bus.emit(
            "whatsapp.message_received",
            {
                "message_context_id": 26650,
                "bridge_session_id": 6,
                "team_member_email": "adit@balizero.com",
                "client_id": 42,
                "direction": "inbound",
                "message_date": "2026-05-15T02:48:33.000Z",
                "preview": "Can you help with my KITAS renewal?",
                "_outbox_id": 15341,
            },
        )

        assert trace.handler_count == 1
        assert trace.errors == []
        insert_sql = conn.execute.await_args.args[0]
        insert_args = conn.execute.await_args.args[1:]
        assert "INSERT INTO interactions" in insert_sql
        assert insert_args[0] == 42
        assert insert_args[1] == 88
        assert insert_args[4] == "inbound"
        assert '"wa_message_context_id": 26650' in insert_args[7]

    @pytest.mark.asyncio
    async def test_client_insert_triggers_background_tasks(self) -> None:
        """Verify that a client INSERT event creates background tasks."""
        bus = EventBus(db_dsn="postgresql://test:test@localhost/test", db_pool=None)
        mock_pool = MagicMock()

        from backend.services.events.handlers import _recent_events, register_handlers
        _recent_events.clear()

        register_handlers(bus, mock_pool)

        # Mock the background task functions
        with patch("backend.services.events.handlers._create_drive_folder", new_callable=AsyncMock), \
             patch("backend.services.events.handlers._log_interaction", new_callable=AsyncMock), \
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

        from backend.services.events.handlers import _recent_events, register_handlers
        _recent_events.clear()

        register_handlers(bus, mock_pool)

        with patch("backend.services.events.handlers._check_client_expiry_on_completion", new_callable=AsyncMock), \
             patch("backend.services.events.handlers.invalidate_cache", create=True, new_callable=AsyncMock):

            trace = await bus.emit("practice.status_changed", {
                "practice_id": 55,
                "client_id": 10,
                "old_status": "approved",
                "new_status": "completed",
            })

            await asyncio.sleep(0.05)

            # 2 subscribers: core _check_client_expiry_on_completion handler
            # + partners.events.handle_practice_status_changed (wired via
            # register_partner_handlers at the tail of register_handlers).
            assert trace.handler_count == 2
            assert trace.errors == []

    @pytest.mark.asyncio
    async def test_compliance_high_sends_telegram(self) -> None:
        """Verify high severity compliance alert sends Telegram."""
        bus = EventBus(db_dsn="postgresql://test:test@localhost/test", db_pool=None)
        mock_pool = MagicMock()

        from backend.services.events.handlers import _recent_events, register_handlers
        _recent_events.clear()

        register_handlers(bus, mock_pool)

        with patch("backend.services.events.handlers._send_admin_telegram", new_callable=AsyncMock), \
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
