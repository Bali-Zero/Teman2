import asyncio
import pytest
import asyncpg
from unittest.mock import AsyncMock, MagicMock
from cell_observatory.collector import Collector


@pytest.mark.asyncio
async def test_bounded_queue_drops_oldest_on_overflow():
    """G1 fix: queue maxsize=10000, drop-oldest on overflow."""
    storage = AsyncMock()
    storage.insert_pulse_event = AsyncMock(return_value=True)
    classifier = AsyncMock()

    collector = Collector(storage=storage, classifier=classifier,
                          classifier_max_inflight=2, classifier_queue_maxsize=3)

    for i in range(10):
        collector._enqueue_for_classification({"outbox_id": i})

    # Queue should be capped at maxsize, oldest dropped
    assert collector._classification_queue.qsize() == 3


@pytest.mark.asyncio
async def test_outbox_replay_on_startup():
    """Replay unconsumed events_outbox rows on collector startup."""
    storage = AsyncMock()
    storage.insert_pulse_event = AsyncMock(return_value=True)
    classifier = AsyncMock()

    collector = Collector(storage=storage, classifier=classifier)

    # NOTE: column is `id` (per migration 144), NOT `outbox_id`. Python-side
    # variable name preserved for downstream contract.
    fake_conn_rows = [
        {
            "id": 1,
            "payload": '{"_outbox_id": 1, "event_version": "v1", "cell_id": "x", "cell_kind": "x", "pulse_id": "x", "pulse_timestamp": "2026-05-01T00:00:00Z", "phase": "x", "sensors": [], "pulse_result": {"classifier_self": "green"}, "homeostatic_state": {}, "scar_signals": [], "metadata": {}}'
        },
    ]

    fake_conn = MagicMock()
    fake_conn.fetch = AsyncMock(return_value=fake_conn_rows)
    fake_conn.execute = AsyncMock()

    await collector._replay_outbox_unconsumed(fake_conn)

    storage.insert_pulse_event.assert_called_once()
    fake_conn.execute.assert_called()  # ack via consumed_at

    # Verify the SELECT uses `id`, not `outbox_id` (regression guard)
    select_call = fake_conn.fetch.call_args[0][0]
    assert "SELECT id, payload" in select_call, f"expected id col, got: {select_call}"
    assert "outbox_id" not in select_call.split("WHERE")[0], (
        "regression: SELECT must not reference outbox_id column"
    )


@pytest.mark.asyncio
async def test_listener_retries_when_keepalive_connection_is_closed(monkeypatch):
    """A stale asyncpg connection must reconnect instead of killing the daemon."""

    class StopLoop(Exception):
        pass

    storage = AsyncMock()
    classifier = AsyncMock()
    collector = Collector(storage=storage, classifier=classifier)

    fake_conn = MagicMock()
    fake_conn.fetch = AsyncMock(return_value=[])
    fake_conn.add_listener = AsyncMock()
    fake_conn.execute = AsyncMock(side_effect=asyncpg.InterfaceError("connection is closed"))
    fake_conn.is_closed.return_value = False
    fake_conn.close = AsyncMock()

    connect = AsyncMock(return_value=fake_conn)
    monkeypatch.setattr("cell_observatory.collector.asyncpg.connect", connect)

    sleep_calls = 0

    async def fake_sleep(_seconds: float) -> None:
        nonlocal sleep_calls
        sleep_calls += 1
        if sleep_calls > 1:
            raise StopLoop

    monkeypatch.setattr("cell_observatory.collector.asyncio.sleep", fake_sleep)

    with pytest.raises(StopLoop):
        await collector.run("postgresql://example", num_workers=0)

    connect.assert_awaited_once_with("postgresql://example")
    fake_conn.close.assert_awaited_once()
